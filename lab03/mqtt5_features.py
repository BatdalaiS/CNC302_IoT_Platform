#!/usr/bin/env python3
"""
CNC302 Лаб 3 — MQTT 5.0-ийн боломжуудыг туршиж хэмжих

Дэд коммандууд:
  expiry     Message Expiry Interval — хугацаа нь дууссан мессеж хүргэгдэх үү?
  alias      Topic Alias — урт сэдвийн нэр сүлжээгээр хэдэн удаа дамжих вэ?
  reqresp    Request/Response — Response Topic + Correlation Data
  shared     Shared Subscription — ачаалал хэрхэн хуваарилагдах вэ?
  reason     Reason Code — татгалзсан шалтгааныг брокер хэрхэн буцаах вэ?
             (Topic Alias Maximum-ыг зориуд хэтрүүлж DISCONNECT 0x94 үүсгэнэ)
  session    Session Expiry — салсан үед мессеж хадгалагдах уу, хугацаа
             дууссаны дараа сесс устах уу? (--expiry секунд)

Стандарт: MQTT 5.0 (OASIS, 2019) — §3.3.2.3.3 Message Expiry, §3.3.2.3.4 Topic
Alias, §3.2.2.3.8 Topic Alias Maximum, §4.10 Request/Response, §4.8.2 Shared
Subscriptions, §3.1.2.11.2 Session Expiry, §2.4 Reason Code.
https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html

Жишээ:
  python mqtt5_features.py --host pi-team03.local expiry
  python mqtt5_features.py --host pi-team03.local shared --subs 3 --count 300
  python mqtt5_features.py --host pi-team03.local reason --topic 'forbidden/x'
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from collections import Counter

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

BASE = "cnc302/lab03"


def client(name: str, a, clean_start=True, session_expiry: int | None = None):
    """MQTT 5.0 клиент. CONNACK-ийн мэдээллийг c.connack dict-д хадгална:
    session_present, reason, TopicAliasMaximum (байхгүй бол 0 — MQTT 5.0 §3.2.2.3.8)."""
    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=name,
                    protocol=mqtt.MQTTv5)
    c.connack = {}
    if a.username:
        c.username_pw_set(a.username, a.password)

    def on_connect(cl, u, flags, rc, p):
        cl.connack.update(
            session_present=bool(flags.session_present), reason=str(rc),
            topic_alias_max=getattr(p, "TopicAliasMaximum", 0) if p else 0)
    c.on_connect = on_connect
    props = Properties(PacketTypes.CONNECT)
    if session_expiry is not None:
        props.SessionExpiryInterval = session_expiry
    c.connect(a.host, a.port, keepalive=30, clean_start=clean_start,
              properties=props)
    return c


def wait_connack(c, timeout: float = 5.0) -> dict:
    """loop_start() хийсний дараа CONNACK ирэхийг хүлээнэ."""
    t_end = time.time() + timeout
    while not c.connack and time.time() < t_end:
        time.sleep(0.02)
    return c.connack


def _vbi(n: int) -> bytes:
    """Variable Byte Integer (MQTT 5.0 §1.5.5)."""
    out = bytearray()
    while True:
        b, n = n % 128, n // 128
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _str(s: str) -> bytes:
    b = s.encode()
    return len(b).to_bytes(2, "big") + b


def raw_alias_probe(a, topic: str):
    """Түүхий CONNECT (v5) → CONNACK-ээс Topic Alias Maximum-ыг уншина →
    түүнээс 1-ээр их alias-тай PUBLISH илгээж, брокерын хариуг буцаана.
    Буцаах: (topic_alias_max | None, хариуны байтууд эсвэл алдааны текст)."""
    import socket
    flags = 0x02                                   # Clean Start
    payload = _str(f"cnc302-raw-{uuid.uuid4().hex[:6]}")
    if a.username:
        flags |= 0x80
        payload += _str(a.username)
        if a.password:
            flags |= 0x40
            payload += _str(a.password)
    vh = _str("MQTT") + bytes([5, flags]) + (30).to_bytes(2, "big") + b"\x00"
    body = vh + payload
    try:
        s = socket.create_connection((a.host, a.port), timeout=3)
        s.sendall(b"\x10" + _vbi(len(body)) + body)
        ack = s.recv(512)
    except OSError as exc:
        return None, str(exc)
    # CONNACK: 0x20, RL, flags, reason, prop_len(VBI), props…
    tam, i = 0, 4
    plen, mult = 0, 1
    while True:
        b = ack[i]; i += 1
        plen += (b & 0x7F) * mult; mult *= 128
        if not b & 0x80:
            break
    end = i + plen
    while i < end:                                 # properties-ийг гүйлгэнэ
        pid = ack[i]; i += 1
        if pid == 0x22:                            # Topic Alias Maximum
            tam = int.from_bytes(ack[i:i + 2], "big"); i += 2
        elif pid in (0x24, 0x25, 0x28, 0x29, 0x2A):  # 1 байт
            i += 1
        elif pid in (0x21, 0x13):                  # 2 байт
            i += 2
        elif pid in (0x11, 0x27):                  # 4 байт
            i += 4
        elif pid == 0x26:                          # User Property: 2 мөр
            for _ in range(2):
                i += 2 + int.from_bytes(ack[i:i + 2], "big")
        else:                                      # UTF-8 мөр / Binary Data
            i += 2 + int.from_bytes(ack[i:i + 2], "big")
    if tam >= 65535:
        s.close()
        return tam, b""
    props = b"\x23" + (tam + 1).to_bytes(2, "big")
    vh = _str(topic) + b"\x00\x01" + _vbi(len(props)) + props
    body = vh + b"bad-alias"
    s.sendall(b"\x32" + _vbi(len(body)) + body)   # PUBLISH, QoS 1
    try:
        resp = s.recv(512)
    except OSError:
        resp = b""
    s.close()
    return tam, resp


def publish_size(topic_len: int, payload_len: int, qos: int, props_len: int) -> int:
    """MQTT 5.0 PUBLISH пакетийн бүтэн хэмжээ (байт), TCP/IP-гүйгээр.
    fixed header 1 + Remaining Length (Variable Byte Integer, §1.5.5)
    + сэдвийн урт 2 + сэдэв + Packet Identifier 2 (QoS>0) + Property Length 1
    + properties + payload  (§2.1, §3.3.2, §3.3.3)."""
    rem = 2 + topic_len + (2 if qos else 0) + 1 + props_len + payload_len
    vbi = 1 if rem < 128 else 2 if rem < 16384 else 3 if rem < 2097152 else 4
    return 1 + vbi + rem


def hr(title: str) -> None:
    print(f"\n{'═' * 68}\n  {title}\n{'═' * 68}")


# ─────────────────────────── 1. Message Expiry ───────────────────────────

def cmd_expiry(a) -> None:
    """
    Хугацаа нь дууссан мессеж хүргэгдэх үү?
    Хадгалагдсан (retained) мессежийг expiry-тэй нийтлээд, хугацаа дуусахаас
    өмнө болон дараа захиалж үзнэ.
    """
    hr("Message Expiry Interval (MQTT 5.0)")
    topic = f"{BASE}/expiry/{uuid.uuid4().hex[:6]}"
    expiry = a.expiry

    pub = client("cnc302-exp-pub", a)
    props = Properties(PacketTypes.PUBLISH)
    props.MessageExpiryInterval = expiry
    pub.loop_start()
    pub.publish(topic, json.dumps({"note": "expiring", "t": time.time()}),
                qos=1, retain=True, properties=props)
    print(f"→ Нийтлэв (retain=True, expiry={expiry}s): {topic}")
    time.sleep(1)

    def try_subscribe(label: str) -> bool:
        got = []
        sub = client(f"cnc302-exp-sub-{uuid.uuid4().hex[:4]}", a)
        sub.on_message = lambda cl, u, m: got.append(m)
        sub.subscribe(topic, qos=1)
        sub.loop_start()
        time.sleep(2.5)
        sub.loop_stop(); sub.disconnect()
        print(f"  {label}: {'ХҮЛЭЭН АВЛАА' if got else 'ирсэнгүй'}")
        if got:
            print(f"    үлдсэн хугацаа (Message Expiry Interval): "
                  f"{getattr(got[0].properties, 'MessageExpiryInterval', 'заагаагүй')}")
        return bool(got)

    before = try_subscribe(f"Хугацаа дуусахаас өмнө ({expiry}s-ээс дотор)")
    wait = expiry + 3
    print(f"→ {wait} секунд хүлээж байна…")
    time.sleep(wait)
    after = try_subscribe("Хугацаа дууссаны дараа")

    pub.publish(topic, "", qos=1, retain=True)   # цэвэрлэнэ
    pub.loop_stop(); pub.disconnect()

    print(f"\nДҮГНЭЛТ: expiry-ээс өмнө={before}, дараа={after}")
    print("Хүлээгдэж буй: өмнө=True, дараа=False.")
    print("Хэрэв дараа нь ч ирсэн бол брокер Message Expiry-г дэмжихгүй байна.")


# ──────────────────────────── 2. Topic Alias ────────────────────────────

def cmd_alias(a) -> None:
    """
    Topic Alias нь урт сэдвийн нэрийг нэг л удаа илгээж, дараа нь 2 байтын
    дугаараар орлуулна. Хэмнэлтийг тооцоолж харуулна.
    """
    hr("Topic Alias (MQTT 5.0)")
    long_topic = (f"{BASE}/ulaanbaatar/campus-north/building-a/floor-3/"
                  f"room-312/hvac/unit-07/telemetry")
    n = a.count
    payload = json.dumps({"t": 24.5})

    c = client("cnc302-alias-pub", a)
    c.loop_start()
    tam = wait_connack(c).get("topic_alias_max", 0)
    print(f"Брокерын CONNACK → Topic Alias Maximum = {tam}")
    if tam < 1:
        # §3.2.2.3.8: байхгүй эсвэл 0 бол клиент alias илгээж БОЛОХГҮЙ.
        print("  Брокер topic alias хүлээж авахгүй — туршилтыг зогсоов.")
        c.loop_stop(); c.disconnect()
        return

    tl, pl = len(long_topic.encode()), len(payload.encode())
    one_plain = publish_size(tl, pl, a.qos, 0)
    one_first = publish_size(tl, pl, a.qos, 3)   # Topic Alias property = 1+2 байт
    one_alias = publish_size(0, pl, a.qos, 3)    # сэдэв 0 урттай + alias
    without = n * one_plain
    with_alias = one_first + (n - 1) * one_alias
    print(f"Сэдэв: {long_topic}\n  урт: {tl} байт, ачаалал: {pl} байт, QoS {a.qos}")
    print(f"\n  Нэг PUBLISH (MQTT түвшин, TCP/IP-гүй):")
    print(f"    alias-гүй : {one_plain} Б   alias-тай (эхнийх): {one_first} Б   "
          f"alias-тай (дараагийнх): {one_alias} Б")
    print(f"  Alias-гүй  : {n} × {one_plain} = {without:,} байт")
    print(f"  Alias-тай  : {one_first} + {n-1} × {one_alias} = {with_alias:,} байт")
    print(f"  Хэмнэлт    : {100*(without-with_alias)/without:.1f}%  "
          f"(PUBACK, TCP/IP толгой, keepalive тооцоонд ороогүй)")

    t0 = time.time()
    info = None
    if a.no_alias:
        # Харьцуулах суурь: яг ижил мессежийг alias-гүй, бүтэн сэдвээр
        for _ in range(n):
            info = c.publish(long_topic, payload, qos=a.qos)
    else:
        props = Properties(PacketTypes.PUBLISH)
        props.TopicAlias = 1
        c.publish(long_topic, payload, qos=a.qos, properties=props)  # 1-р удаа: нэр + alias
        empty = Properties(PacketTypes.PUBLISH)
        empty.TopicAlias = 1
        for _ in range(n - 1):
            info = c.publish("", payload, qos=a.qos, properties=empty)  # цаашид зөвхөн alias
    if info is not None:
        info.wait_for_publish(timeout=30)          # бүгд илгээгдтэл хүлээнэ
    c.disconnect(); c.loop_stop()
    print(f"\n→ {n} мессеж {'ALIAS-ГҮЙ' if a.no_alias else 'alias-тай'} илгээв, "
          f"{time.time()-t0:.2f} сек")
    print("Брокерын хүлээн авсан байтын тоолуурыг (EMQX: bytes.received, "
          "mosquitto: $SYS/broker/bytes/received) өмнө/дараа нь харьцуул.")


# ─────────────────────────── 3. Request/Response ───────────────────────────

def cmd_reqresp(a) -> None:
    """
    MQTT 5.0-д хүсэлт/хариултын загвар протоколын түвшинд дэмжигдсэн:
    Response Topic + Correlation Data.
    """
    hr("Request / Response (MQTT 5.0)")
    req_topic = f"{BASE}/rpc/request"
    resp_topic = f"{BASE}/rpc/response/{uuid.uuid4().hex[:8]}"

    # ── хариулагч (төхөөрөмж) ──
    responder = client("cnc302-responder", a)

    def on_req(cl, u, m):
        rt = m.properties.ResponseTopic
        cd = m.properties.CorrelationData
        print(f"  [хариулагч] хүсэлт ирлээ: {m.payload.decode()}")
        print(f"              ResponseTopic={rt}")
        print(f"              CorrelationData={cd!r}")
        p = Properties(PacketTypes.PUBLISH)
        p.CorrelationData = cd
        cl.publish(rt, json.dumps({"ok": True, "uptime_s": 12345}),
                   qos=1, properties=p)

    responder.on_message = on_req
    responder.subscribe(req_topic, qos=1)
    responder.loop_start()

    # ── хүсэгч (платформ) ──
    got = []
    requester = client("cnc302-requester", a)
    requester.on_message = lambda cl, u, m: got.append(m)
    requester.subscribe(resp_topic, qos=1)
    requester.loop_start()
    time.sleep(0.5)

    corr = uuid.uuid4().bytes
    p = Properties(PacketTypes.PUBLISH)
    p.ResponseTopic = resp_topic
    p.CorrelationData = corr
    t0 = time.time()
    requester.publish(req_topic, json.dumps({"method": "getStatus"}),
                      qos=1, properties=p)

    deadline = time.time() + 5
    while not got and time.time() < deadline:
        time.sleep(0.05)
    rtt = (time.time() - t0) * 1000

    if got:
        m = got[0]
        ok = m.properties.CorrelationData == corr
        print(f"\n  [хүсэгч] хариу: {m.payload.decode()}")
        print(f"           RTT = {rtt:.1f} мс")
        print(f"           CorrelationData таарсан уу: {ok}")
    else:
        print("\n  ХАРИУ ИРСЭНГҮЙ")

    for c in (responder, requester):
        c.loop_stop(); c.disconnect()

    print("\nДҮГНЭЛТ: MQTT 3.1.1-д энэ загварыг гараар (сэдвийн нэршлээр) хийдэг байсан.")
    print("5.0-д протоколын хэсэг тул брокер, номын сангууд шууд дэмжинэ.")


# ──────────────────────── 4. Shared Subscription ────────────────────────

def cmd_shared(a) -> None:
    """
    $share/<group>/<topic> — ачаалал захиалагчид хооронд хуваарилагдана.
    Энгийн захиалгад БҮХ захиалагч БҮХ мессежийг авдаг.
    """
    hr("Shared Subscription ($share)")
    topic = f"{BASE}/shared/{uuid.uuid4().hex[:6]}"
    n_subs, n_msg = a.subs, a.count

    def run(shared: bool) -> Counter:
        tally: Counter = Counter()
        subs = []
        filt = f"$share/cnc302grp/{topic}" if shared else topic
        for i in range(n_subs):
            name = f"sub{i}"
            c = client(f"cnc302-sh-{shared}-{i}", a)
            c.on_message = (lambda nm: (lambda cl, u, m: tally.update([nm])))(name)
            c.subscribe(filt, qos=1)
            c.loop_start()
            subs.append(c)
        time.sleep(0.7)

        pub = client(f"cnc302-sh-pub-{shared}", a)
        pub.loop_start()
        for i in range(n_msg):
            pub.publish(topic, json.dumps({"i": i}), qos=1)
            time.sleep(0.002)
        time.sleep(2.0)
        pub.loop_stop(); pub.disconnect()
        for c in subs:
            c.loop_stop(); c.disconnect()
        return tally

    print(f"\nA) Энгийн захиалга — {n_subs} захиалагч, {n_msg} мессеж")
    plain = run(False)
    for k in sorted(plain):
        print(f"   {k}: {plain[k]:5d}")
    print(f"   НИЙТ хүлээн авсан: {sum(plain.values())}  "
          f"(хүлээгдэж буй ≈ {n_subs * n_msg})")

    time.sleep(1)
    print(f"\nB) Хуваалцсан захиалга — {n_subs} захиалагч, {n_msg} мессеж")
    sh = run(True)
    for k in sorted(sh):
        print(f"   {k}: {sh[k]:5d}")
    print(f"   НИЙТ хүлээн авсан: {sum(sh.values())}  (хүлээгдэж буй ≈ {n_msg})")

    if sh:
        vals = list(sh.values())
        bal = 100 * (max(vals) - min(vals)) / max(sum(vals) / len(vals), 1)
        print(f"\n   Тэнцвэржилтийн хазайлт: {bal:.1f}% "
              f"(0% = төгс тэнцвэртэй)")
    print("\nДҮГНЭЛТ: Хуваалцсан захиалга нь хэрэглэгчийг ХЭВТЭЭ ӨРГӨТГӨХ боломж өгнө.")


# ────────────────────────────── 5. Reason Code ──────────────────────────────

def cmd_reason(a) -> None:
    """
    MQTT 5.0-д брокер татгалзсан шалтгаанаа тоогоор буцаана.
    3.1.1-д зөвхөн 'холболт таслагдлаа' л мэдэгддэг байсан.
    """
    hr("Reason Code (MQTT 5.0)")
    topic = a.topic or f"{BASE}/reason/test"
    results = []

    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="cnc302-reason",
                    protocol=mqtt.MQTTv5)
    if a.username:
        c.username_pw_set(a.username, a.password)

    def on_connect(cl, u, f, rc, p=None):
        print(f"  CONNACK reason code: {rc}  ({getattr(rc, 'getName', lambda: '')()})")
        results.append(("connect", str(rc)))

    def on_subscribe(cl, u, mid, rcs, p=None):
        for rc in rcs:
            print(f"  SUBACK  reason code: {rc}")
            results.append(("subscribe", str(rc)))

    def on_publish(cl, u, mid, rc=None, p=None):
        if rc is not None:
            print(f"  PUBACK  reason code: {rc}")
            results.append(("publish", str(rc)))

    c.on_connect, c.on_subscribe, c.on_publish = on_connect, on_subscribe, on_publish
    c.connect(a.host, a.port, keepalive=30)
    c.loop_start()
    time.sleep(0.5)
    c.subscribe(topic, qos=2)
    time.sleep(0.5)
    c.publish(topic, "тест", qos=1)
    time.sleep(1.0)
    c.disconnect(); c.loop_stop()

    # ── Зориудаар алдаа: брокерын зөвшөөрснөөс их Topic Alias илгээнэ ──
    # §3.3.2.3.4: клиент CONNACK-ийн Topic Alias Maximum-аас их alias
    # илгээж болохгүй. Брокер DISCONNECT 0x94 (148) буцаана гэж хүлээнэ.
    # paho-mqtt 2.1.0 нь зөвхөн reason code-той (Remaining Length = 1)
    # DISCONNECT-ийг задлахдаа кодыг 0 гэж мэдээлдэг тул энд пакетийг
    # түүхий сокетоор илгээж, брокерын хариуг байтаар нь уншина.
    print("\n  Алдаа үүсгэх туршилт: Topic Alias > Topic Alias Maximum")
    tam, resp = raw_alias_probe(a, topic)
    if tam is None:
        print(f"  Холбогдож чадсангүй: {resp}")
    elif tam >= 65535:
        print(f"  Topic Alias Maximum = {tam} (дээд боломжит утга) — хэтрүүлэх боломжгүй.")
    elif resp[:1] == b"\xe0" and len(resp) >= 3:
        code = resp[2]
        print(f"  Брокерын хариу: {resp.hex(' ')}  → DISCONNECT, reason code "
              f"{code} (0x{code:02x})  [илгээсэн alias={tam + 1}, дээд={tam}]")
    else:
        print(f"  Брокерын хариу: {resp.hex(' ') or '(хоосон — холболт хаагдав)'}"
              " — ажиглалт болгон тэмдэглэ.")

    print("\nТайлбар (MQTT 5.0 §2.4, Хүснэгт 2-6):")
    print("  0   0x00 Success / Granted QoS 0 — амжилттай")
    print("  2   0x02 Granted QoS 2           — SUBACK: QoS 2-оор захиалга зөвшөөрөв")
    print("  135 0x87 Not authorized          — эрхгүй (ACL/authorization дүрмээр)")
    print("  144 0x90 Topic Name invalid      — сэдвийн нэр буруу")
    print("  148 0x94 Topic Alias invalid     — alias хязгаараас хэтэрсэн (DISCONNECT)")
    print("  151 0x97 Quota exceeded          — хязгаар хэтэрсэн")
    print("\nЭрхгүй (135) тохиолдлыг үзэхийн тулд EMQX самбар дээр Access Control → "
          "Authorization дүрэм нэмээд дахин ажиллуулна уу.")


# ──────────────────────────── 6. Session Expiry ────────────────────────────

def cmd_session(a) -> None:
    """
    Session Expiry Interval — клиент салсны дараа брокер түүний захиалга,
    дараалалд байгаа мессежийг хэдэн секунд хадгалах вэ?
    """
    hr("Session Expiry Interval (MQTT 5.0)")
    topic = f"{BASE}/session/{uuid.uuid4().hex[:6]}"
    cid = f"cnc302-persist-{uuid.uuid4().hex[:6]}"

    print(f"1) {cid} нь SessionExpiry={a.expiry}s-тэй холбогдож захиална")
    c1 = client(cid, a, clean_start=True, session_expiry=a.expiry)
    c1.subscribe(topic, qos=1)
    c1.loop_start(); time.sleep(1)
    c1.disconnect(); c1.loop_stop()
    print("2) Салгав")

    print("3) Салсан хойно 5 мессеж нийтэлнэ")
    pub = client("cnc302-sess-pub", a)
    pub.loop_start()
    for i in range(5):
        pub.publish(topic, json.dumps({"i": i}), qos=1)
    time.sleep(1)
    pub.disconnect(); pub.loop_stop()

    print("4) Ижил client_id-гаар clean_start=False-ээр буцаж холбогдоно")
    got = []
    c2 = client(cid, a, clean_start=False, session_expiry=a.expiry)
    c2.on_message = lambda cl, u, m: got.append(json.loads(m.payload))
    c2.loop_start(); time.sleep(3)
    sp = c2.connack.get("session_present")
    c2.disconnect(); c2.loop_stop()

    print(f"\n   CONNACK session_present = {sp}")
    print(f"   Салсан хугацаанд хуримтлагдсанаас хүлээн авсан: {len(got)}/5")
    print("   Хүлээгдэж буй: session_present=True, 5/5")

    # ── Хугацаа дууссаны дараа сесс устсан уу? (§3.1.2.11.2, §4.1.1) ──
    wait = a.expiry + 3
    print(f"\n5) Дахин салгаад {wait} секунд хүлээнэ (Session Expiry {a.expiry}s-ээс урт)…")
    time.sleep(wait)
    pub = client("cnc302-sess-pub2", a)
    pub.loop_start()
    for i in range(5):
        pub.publish(topic, json.dumps({"i": 100 + i}), qos=1)
    time.sleep(1)
    pub.disconnect(); pub.loop_stop()
    got2 = []
    c3 = client(cid, a, clean_start=False, session_expiry=a.expiry)
    c3.on_message = lambda cl, u, m: got2.append(m)
    c3.loop_start(); time.sleep(3)
    sp2 = c3.connack.get("session_present")
    c3.disconnect(); c3.loop_stop()
    print(f"   CONNACK session_present = {sp2}, хүлээн авсан: {len(got2)}/5")
    print("   Хүлээгдэж буй: session_present=False, 0/5 — сесс ба захиалга устсан")
    print("\nДҮГНЭЛТ: Энэ нь сүлжээ тасалдсан IoT төхөөрөмжид чухал. "
          "Гэхдээ хадгалагдсан сесс бүр брокерын санах ой иднэ — "
          "Лаб 4-т 1000 холболт дээр үүнийг мэдэрнэ.")


# ──────────────────────────────── main ────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(
        description="MQTT 5.0-ийн боломжуудын туршилт",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--username")
    p.add_argument("--password")
    p.add_argument("--qos", type=int, default=1, choices=[0, 1, 2])
    p.add_argument("--count", type=int, default=200)
    p.add_argument("--subs", type=int, default=3)
    p.add_argument("--expiry", type=int, default=10)
    p.add_argument("--topic")
    p.add_argument("--no-alias", action="store_true",
                   help="alias: харьцуулах суурь — ижил мессежийг alias-гүй илгээнэ")
    p.add_argument("cmd", choices=["expiry", "alias", "reqresp", "shared",
                                   "reason", "session", "all"])
    a = p.parse_args()

    table = {"expiry": cmd_expiry, "alias": cmd_alias, "reqresp": cmd_reqresp,
             "shared": cmd_shared, "reason": cmd_reason, "session": cmd_session}
    if a.cmd == "all":
        for name, fn in table.items():
            try:
                fn(a)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{name}] АЛДАА: {exc}", file=sys.stderr)
    else:
        table[a.cmd](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
