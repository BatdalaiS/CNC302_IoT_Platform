#!/usr/bin/env python3
"""
CNC302 Лаб 3 — MQTT 5.0-ийн боломжуудыг туршиж хэмжих

Дэд коммандууд:
  expiry     Message Expiry Interval — хугацаа нь дууссан мессеж хүргэгдэх үү?
  alias      Topic Alias — урт сэдвийн нэр сүлжээгээр хэдэн удаа дамжих вэ?
  reqresp    Request/Response — Response Topic + Correlation Data
  shared     Shared Subscription — ачаалал хэрхэн хуваарилагдах вэ?
  reason     Reason Code — татгалзсан шалтгааныг брокер хэрхэн буцаах вэ?
  session    Session Expiry — салсан үед мессеж хадгалагдах уу?

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
    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=name,
                    protocol=mqtt.MQTTv5)
    if a.username:
        c.username_pw_set(a.username, a.password)
    props = Properties(PacketTypes.CONNECT)
    if session_expiry is not None:
        props.SessionExpiryInterval = session_expiry
    c.connect(a.host, a.port, keepalive=30, clean_start=clean_start,
              properties=props)
    return c


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

    print(f"Сэдэв: {long_topic}\n  урт: {len(long_topic)} байт")
    without = n * (2 + len(long_topic) + len(payload))
    with_alias = (2 + len(long_topic) + len(payload) + 3) + (n - 1) * (2 + 0 + len(payload) + 3)
    print(f"\n  Alias-гүй  : {n} × ({len(long_topic)} + {len(payload)}) ≈ {without:,} байт")
    print(f"  Alias-тай  : ≈ {with_alias:,} байт")
    print(f"  Хэмнэлт    : {100*(without-with_alias)/without:.1f}%")

    c = client("cnc302-alias-pub", a)
    c.loop_start()
    props = Properties(PacketTypes.PUBLISH)
    props.TopicAlias = 1
    t0 = time.time()
    c.publish(long_topic, payload, qos=a.qos, properties=props)  # 1-р удаа: нэр + alias
    empty = Properties(PacketTypes.PUBLISH)
    empty.TopicAlias = 1
    for _ in range(n - 1):
        c.publish("", payload, qos=a.qos, properties=empty)      # цаашид зөвхөн alias
    c.loop_stop(); c.disconnect()
    print(f"\n→ {n} мессеж илгээв, {time.time()-t0:.2f} сек")
    print("Брокерын самбарын 'Bytes received' үзүүлэлтийг өмнө/дараа нь харьцуул.")


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
    c.loop_stop(); c.disconnect()

    print("\nТайлбар:")
    print("  0 / Success            — амжилттай")
    print("  135 / Not authorized   — эрхгүй (EMQX-д ACL тохируулсан үед)")
    print("  151 / Quota exceeded   — хязгаар хэтэрсэн")
    print("  144 / Topic Name invalid")
    print("\nЭрхгүй тохиолдлыг үзэхийн тулд EMQX самбар дээр Access Control → "
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
    c1.loop_stop(); c1.disconnect()
    print("2) Салгав")

    print("3) Салсан хойно 5 мессеж нийтэлнэ")
    pub = client("cnc302-sess-pub", a)
    pub.loop_start()
    for i in range(5):
        pub.publish(topic, json.dumps({"i": i}), qos=1)
    time.sleep(1)
    pub.loop_stop(); pub.disconnect()

    print("4) Ижил client_id-гаар clean_start=False-ээр буцаж холбогдоно")
    got = []
    c2 = client(cid, a, clean_start=False, session_expiry=a.expiry)
    c2.on_message = lambda cl, u, m: got.append(json.loads(m.payload))
    c2.loop_start(); time.sleep(3)
    c2.loop_stop(); c2.disconnect()

    print(f"\n   Салсан хугацаанд хуримтлагдсанаас хүлээн авсан: {len(got)}/5")
    print("   Хүлээгдэж буй: 5 (сесс хадгалагдсан бол)")
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
