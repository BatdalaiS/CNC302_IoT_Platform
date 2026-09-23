#!/usr/bin/env python3
"""
CNC302 Лаб 5 — Өгөгдлийн бүрэн бүтэн байдлыг ХЭМЖИХ

Эвдрэлийн туршилтын гол хэрэгсэл. "Өгөгдөл алдагдсан уу?" гэдэгт
таамгаар биш, ТООГООР хариулна.

Ажиллах зарчим:
  1. publish — дугаарласан мессежийг тогтмол хурдаар илгээж, илгээснээ
     локал файлд бүртгэнэ (энэ бол "үнэний эх сурвалж")
  2. verify  — цаг цувааны сангаас тэр дугааруудыг асууж, аль нь
     хүрээгүйг олно → алдагдлын хувь, тасалдлын урт, сэргэх хугацаа

── ХОЁР ЗАМ (--via) ────────────────────────────────────────────────────────
Стек хоёр хостод хуваагдсан тул мессеж хоёр өөр замаар InfluxDB хүрч болно:

  --via direct  зөөврийн компьютерийн EMQX рүү ШУУД. Ирмэгийн гүүр оролцохгүй.
  --via edge    Pi 3B дээрх mosquitto руу. Тэндээс ГҮҮР (bridge) нь үүл рүү
                дамжуулна. Өгсөх урсгал тасрахад гүүр мессежийг САНАХ ОЙН дараалалд
                хадгалж (store-and-forward), холбоос сэргэхэд дамжуулна. Дараалал
                нь mosquitto.db файлд ЗӨВХӨН autosave_interval тутамд болон
                mosquitto хэвийн унтрахад бичигдэнэ — цахилгаан тасрахад сүүлийн
                хадгалалтаас хойшхи дараалал алдагдана. ЭНЭ БОЛ ЛАБ 5-ын гол
                хэмжилт. `--via` нь JSONL болон meta-д бичигдэнэ.

── ГҮҮР УНАСАН ҮЕИЙН АЛДАГДЛЫГ ТУСАД НЬ (--bridge-log) ─────────────────────
Гүүрний төлөв `cnc302/<site>/<area>/<line>/<device>/bridge/state` сэдэвт
нийтлэгддэг (1 = холбогдсон, 0 = тасарсан). Түүнийг зэрэг бичиж авбал verify
нь алдагдлыг ГҮҮР УНАСАН ба АЖИЛЛАЖ БАЙСАН үе гэж ХУВААЖ тайлагнана:

  mosquitto_sub -h localhost -F '{"ts":%U,"state":%p}' \\
      -t 'cnc302/shutis/mhts/lab/pi3b-01/bridge/state' > lab05/out/bridge.jsonl

Store-and-forward зөв ажиллаж байвал гүүр унасан үеийн алдагдал ч 0 байх
ёстой — ЯГ ЭНЭ ЗӨРҮҮГ хэмжинэ.

⚠ Гүүр тасралтыг ШУУД мэддэггүй: keepalive_interval (анхдагч 60 с) дуусч
PINGRESP ирэхгүй болсон үед л "0" нийтэлнэ. Тиймээс 60 секундын тасалдалд
bridge.jsonl дээр "0" огт гарахгүй байж болно. Үүний тулд --cut-log нь
failure_inject.sh-ийн бичсэн БОДИТ тасалдлын цагийг (uplink-events.jsonl,
ижил {"ts":…,"state":0|1} хэлбэр) ашиглаж алдагдлыг хувааж, MTTR-ыг
тооцно:

  python data_integrity.py verify --influx http://192.168.1.100:8181 \\
      --run-id run1 --bridge-log lab05/out/bridge.jsonl \\
      --cut-log lab05/out/uplink-events.jsonl

Жишээ:
  # 1-р терминал (Pi дээр): 5 минут, секундэд 10 мессеж, ирмэгээр дамжина
  python data_integrity.py publish --via edge --host localhost \\
      --rate 10 --seconds 300 --run-id run1

  # 2-р терминал (Pi дээр): энэ хооронд өгсөх урсгалыг таслана
  bash failure_inject.sh uplink-down 30

  # Дараа нь шалгана (InfluxDB нь зөөврийн компьютер дээр)
  python data_integrity.py verify --influx http://192.168.1.100:8181 \\
      --run-id run1 --bridge-log lab05/out/bridge.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import paho.mqtt.client as mqtt
import requests
from paho.mqtt.enums import CallbackAPIVersion

# UNS: cnc302/<site>/<area>/<line>/<device>/<channel>
# Ирмэгийн гүүр нь cnc302/<site>/# сэдвийг л үүл рүү дамжуулдаг тул site нь
# edge/.env-ийн SITE-тэй ЗААВАЛ таарна (анхдагч: shutis/mhts/lab).
TOPIC = "cnc302/shutis/mhts/lab/integrity/telemetry"
MEASUREMENT = "integrity"

VIA_LABEL = {
    "edge": "Pi 3B → ирмэгийн mosquitto → гүүр → EMQX (store-and-forward)",
    "direct": "EMQX рүү шууд (гүүр оролцохгүй)",
}


# ────────────────────────────── PUBLISH ──────────────────────────────

def cmd_publish(a) -> int:
    os.makedirs(a.outdir, exist_ok=True)
    logpath = os.path.join(a.outdir, f"{a.run_id}-sent.jsonl")

    print(f"→ Зам (--via): {a.via} — {VIA_LABEL[a.via]}", file=sys.stderr)
    print(f"→ Брокер: {a.host}:{a.port}   сэдэв: {TOPIC}", file=sys.stderr)
    if a.via == "edge":
        print("→ Санамж: гүүрний төлөвийг зэрэг бичиж авбал verify нь алдагдлыг "
              "гүүр унасан/ажилласан үеэр нь хуваана (--bridge-log).",
              file=sys.stderr)

    sent = 0
    failed = 0
    disconnects = 0
    reconnects = 0
    connected = {"v": False}
    finishing = {"v": False}      # төгсгөлийн хэвийн disconnect-ийг тоолохгүй

    def on_connect(cl, u, f, rc, p=None):
        if rc == 0:
            connected["v"] = True

    def on_disconnect(cl, u, flags, rc, p=None):
        nonlocal disconnects
        connected["v"] = False
        if finishing["v"]:
            return
        disconnects += 1
        print(f"  ⚠ [{time.strftime('%H:%M:%S')}] холболт тасарлаа (rc={rc})",
              file=sys.stderr)

    c = mqtt.Client(CallbackAPIVersion.VERSION2,
                    client_id=f"integrity-{a.run_id}", protocol=mqtt.MQTTv5)
    c.on_connect = on_connect
    c.on_disconnect = on_disconnect
    # автоматаар дахин холбогдох (IoT төхөөрөмжийн хэвийн зан төлөв)
    c.reconnect_delay_set(min_delay=1, max_delay=8)
    try:
        c.connect(a.host, a.port, keepalive=15)
    except Exception as exc:  # noqa: BLE001
        print(f"Эхний холболт амжилтгүй: {exc}", file=sys.stderr)
        return 2
    c.loop_start()
    # Эхний холболтыг хүлээнэ — эс бөгөөс эхний хэдэн мессеж "тасалдал" болж тоологдоно
    t_wait = time.time() + 10
    while not connected["v"] and time.time() < t_wait:
        time.sleep(0.05)

    interval = 1.0 / a.rate
    t_end = time.time() + a.seconds
    was_down = False

    with open(logpath, "w", encoding="utf-8") as log:
        while time.time() < t_end:
            if connected["v"] and was_down:
                reconnects += 1
                print(f"  ✓ [{time.strftime('%H:%M:%S')}] дахин холбогдлоо",
                      file=sys.stderr)
                was_down = False
            if not connected["v"]:
                was_down = True

            ts = int(time.time() * 1000)
            payload = {"run_id": a.run_id, "seq": sent, "ts": ts,
                       "value": round(20 + (sent % 100) * 0.1, 2)}
            info = c.publish(TOPIC, json.dumps(payload), qos=a.qos)
            ok = info.rc == mqtt.MQTT_ERR_SUCCESS
            if ok:
                sent += 1
            else:
                failed += 1
            # `via` мөр бүрт бичигдэнэ: нэг фолдерт хоёр замын лог хамт байхад
            # хожим ялгах боломжтой байх ёстой.
            log.write(json.dumps({**payload, "published": ok, "via": a.via}) + "\n")

            if sent % (a.rate * 10) == 0 and sent:
                print(f"  [{time.strftime('%H:%M:%S')}] илгээв={sent} "
                      f"амжилтгүй={failed} тасалдал={disconnects}",
                      file=sys.stderr)
            time.sleep(interval)

    finishing["v"] = True
    c.disconnect()
    c.loop_stop()

    meta = {"run_id": a.run_id, "via": a.via, "broker": f"{a.host}:{a.port}",
            "topic": TOPIC, "qos": a.qos,
            "rate": a.rate, "seconds": a.seconds,
            "attempted": sent + failed, "published_ok": sent,
            "publish_failed": failed,
            "disconnects": disconnects, "reconnects": reconnects}
    with open(os.path.join(a.outdir, f"{a.run_id}-meta.json"), "w",
              encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"\n{'═'*56}\n  ИЛГЭЭЛТИЙН ДҮН — {a.run_id}\n{'═'*56}")
    for k, v in meta.items():
        print(f"  {k:<18} {v}")
    print(f"\n  Лог: {logpath}")
    print(f"  Дараа нь: python data_integrity.py verify --run-id {a.run_id}")
    return 0


# ────────────────────────────── VERIFY ──────────────────────────────

def query_influx3(base: str, db: str, run_id: str,
                  token: str | None = None) -> dict[int, int | None]:
    """
    InfluxDB 3 Core: POST /api/v3/query_sql, JSON биед db, q, format.
    format=json нь мөр бүрийг объект болгосон JSON массив буцаана.
    Буцаах утга: {seq: rx_ms}. rx_ms = Node-RED мессежийг хүлээн авсан
    цаг (мс, ЗӨӨВРИЙН КОМПЬЮТЕРИЙН цаг) — MTTR-ыг үүгээр тооцно.
    """
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = requests.post(
        f"{base.rstrip('/')}/api/v3/query_sql",
        json={"db": db,
              # SELECT * — хуучин урсгалаар бичсэн мөрөнд rx_ms байхгүй ч болно
              "q": f"SELECT * FROM {MEASUREMENT} WHERE run_id = '{run_id}'",
              "format": "json"},
        headers=headers, timeout=60,
    )
    if r.status_code >= 400:
        print(f"\n✗ InfluxDB асуулга амжилтгүй ({r.status_code}): {r.text[:300]}",
              file=sys.stderr)
        print(f"  '{MEASUREMENT}' хүснэгт үүсээгүй байж болно — Node-RED урсгал "
              "integrity мессежийг бичиж байгаа эсэхийг шалга (Алхам 2).",
              file=sys.stderr)
        r.raise_for_status()
    out: dict[int, int | None] = {}
    for row in r.json():
        if row.get("seq") is None:
            continue
        rx = row.get("rx_ms")
        out[int(row["seq"])] = int(rx) if rx is not None else None
    return out


def query_influx2(base: str, org: str, bucket: str, token: str,
                  run_id: str) -> set[int]:
    flux = (f'from(bucket:"{bucket}") |> range(start:-24h) '
            f'|> filter(fn:(r) => r._measurement == "{MEASUREMENT}") '
            f'|> filter(fn:(r) => r.run_id == "{run_id}") '
            f'|> filter(fn:(r) => r._field == "seq")')
    r = requests.post(
        f"{base.rstrip('/')}/api/v2/query",
        params={"org": org},
        headers={"Authorization": f"Token {token}",
                 "Content-Type": "application/vnd.flux",
                 "Accept": "application/csv"},
        data=flux, timeout=60,
    )
    r.raise_for_status()
    out: set[int] = set()
    for line in r.text.splitlines():
        parts = line.split(",")
        if len(parts) > 6 and parts[0] == "":
            try:
                out.add(int(float(parts[6])))
            except ValueError:
                continue
    return out


def find_gaps(sent: list[int], got: set[int]) -> list[tuple[int, int]]:
    """Тасралтгүй алдагдсан хэсгүүдийг (эхлэл, төгсгөл) хэлбэрээр буцаана."""
    gaps = []
    start = None
    for s in sent:
        if s not in got:
            if start is None:
                start = s
        elif start is not None:
            gaps.append((start, s - 1))
            start = None
    if start is not None:
        gaps.append((start, sent[-1]))
    return gaps


# ───────────────── ГҮҮРНИЙ ТӨЛӨВ (bridge/state) — цэвэр функцууд ─────────────────
# Эдгээр функц нь сүлжээ, файл, цаг ашиглахгүй — зөвхөн өгөгдөл хувиргана.
# Тиймээс find_gaps-ийн адил нэгж тестээр шалгахад хялбар.

def _to_ms(v: float) -> int:
    """Секунд эсвэл миллисекундыг миллисекунд болгож жигдрүүлнэ."""
    v = float(v)
    return int(v) if v > 1e12 else int(v * 1000)


def parse_bridge_events(lines) -> list[tuple[int, int]]:
    """
    JSONL мөрүүдээс (ts_ms, state) хосуудыг эрэмбэлж гаргана. state: 1|0.
    Танигдах түлхүүрүүд: ts/time/timestamp ба state/value/payload.
    Танихгүй, хоосон, эвдэрсэн мөрийг чимээгүй алгасна.
    """
    out: list[tuple[int, int]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except (ValueError, TypeError):
            continue
        if not isinstance(d, dict):
            continue
        ts = d.get("ts", d.get("time", d.get("timestamp")))
        st = d.get("state", d.get("value", d.get("payload")))
        if ts is None or st is None:
            continue
        try:
            out.append((_to_ms(ts), 1 if int(str(st).strip()) else 0))
        except (ValueError, TypeError):
            continue
    out.sort(key=lambda e: e[0])
    return out


def bridge_down_intervals(events: list[tuple[int, int]],
                          end_ms: int | None = None) -> list[tuple[int, int]]:
    """
    (ts, state) цувааг ГҮҮР УНАСАН завсруудын жагсаалт болгоно.
    Төлөв 0 болсноос 1 болтол = нэг завсар. Эцэст нь 0-оор дуусвал `end_ms`
    хүртэл (эсвэл дуусаагүй гэж үзэж хамгийн том утга хүртэл) үргэлжилнэ.
    """
    intervals: list[tuple[int, int]] = []
    down_from: int | None = None
    for ts, st in events:
        if st == 0 and down_from is None:
            down_from = ts
        elif st == 1 and down_from is not None:
            intervals.append((down_from, ts))
            down_from = None
    if down_from is not None:
        intervals.append((down_from, end_ms if end_ms is not None else 2**62))
    return intervals


def in_any_interval(ts: int, intervals: list[tuple[int, int]]) -> bool:
    return any(lo <= ts < hi for lo, hi in intervals)


def split_by_bridge(seqs: list[int], ts_by_seq: dict[int, int],
                    down: list[tuple[int, int]]) -> tuple[list[int], list[int]]:
    """seq-үүдийг (гүүр УНАСАН үед илгээсэн, ГҮҮР АЖИЛЛАЖ байхад илгээсэн)."""
    while_down, while_up = [], []
    for s in seqs:
        ts = ts_by_seq.get(s)
        if ts is not None and in_any_interval(ts, down):
            while_down.append(s)
        else:
            while_up.append(s)
    return while_down, while_up


def report_bridge_split(sent_ok, lost, ts_by_seq, down,
                        title: str = "ГҮҮРНИЙ ТӨЛӨВӨӨР ХУВААСАН АЛДАГДАЛ",
                        key: str = "bridge") -> dict:
    """Тасарсан/ажилласан үеийн алдагдлыг тусад нь хэвлэж, дүнг буцаана.
    key="bridge" → гүүрний өөрийн мэдээлсэн төлөв (bridge/state),
    key="cut"    → failure_inject.sh-ийн бодит тасалдлын цаг."""
    sent_down, sent_up = split_by_bridge(sent_ok, ts_by_seq, down)
    lost_down, lost_up = split_by_bridge(lost, ts_by_seq, down)

    total_down_s = sum(
        (min(hi, 2**62) - lo) / 1000.0 for lo, hi in down if hi < 2**62)
    print(f"\n  ── {title} ──")
    print(f"  Тасарсан удаа         : {len(down)}  "
          f"(нийт ~{total_down_s:.1f} сек)")
    print(f"  {'':<22} {'илгээсэн':>10} {'алдагдсан':>10} {'алдалт%':>9}")
    for name, s_list, l_list in (("ТАСАРСАН үед", sent_down, lost_down),
                                 ("АЖИЛЛАЖ байхад", sent_up, lost_up)):
        pct = 100.0 * len(l_list) / max(len(s_list), 1)
        print(f"  {name:<22} {len(s_list):>10} {len(l_list):>10} {pct:>8.2f}%")

    if not down:
        print("  ⚠ Тасралт бүртгэгдээгүй. key=bridge бол: гүүр keepalive-аар "
              "тасралтыг илрүүлэхээс\n    өмнө өгсөх урсгал сэргэсэн байж болно "
              "(keepalive_interval) — --cut-log-оор шалга.")
    elif sent_down and not lost_down:
        print("  ✓ Тасарсан үеийн мессеж БҮГД хүрсэн — store-and-forward "
              "ажиллаж байна.")
    elif lost_down:
        print("  ⚠ Тасарсан үед мессеж алдагдсан. Шалтгаан нь ихэвчлэн: "
              "cleansession true,\n    max_queued_messages дүүрсэн (ШИНЭ мессеж "
              "хаягдана), QoS 0 (гүүр тасралтыг\n    илрүүлэхээс өмнө TCP руу "
              "бичигдсэн эсвэл queue_qos0_messages false), эсвэл\n    mosquitto "
              "autosave-аас өмнө хүчээр унтарсан.")

    return {
        f"{key}_down_events": len(down),
        f"{key}_down_seconds": round(total_down_s, 1),
        f"sent_while_{key}_down": len(sent_down),
        f"lost_while_{key}_down": len(lost_down),
        f"loss_pct_while_{key}_down": round(
            100.0 * len(lost_down) / max(len(sent_down), 1), 3),
        f"sent_while_{key}_up": len(sent_up),
        f"lost_while_{key}_up": len(lost_up),
        f"loss_pct_while_{key}_up": round(
            100.0 * len(lost_up) / max(len(sent_up), 1), 3),
    }


def mttr_after_cuts(sent_ok, rx_by_seq, ts_by_seq, down) -> dict:
    """
    MTTR (курсын тодорхойлолт): тасалдал дууссан мөчөөс тухайн тасалдлын
    үеэр илгээсэн мессежийн СҮҮЛЧИЙНХ нь санд хүрэх (rx_ms) хүртэлх хугацаа.
    rx_ms нь зөөврийн компьютерийн цаг, тасалдлын цаг нь Pi-гийн цаг — хоёр
    хостын цаг NTP-ээр тохирсон байх ЁСТОЙ (timedatectl-оор шалга).
    """
    out = []
    for lo, hi in down:
        if hi >= 2**62:
            continue
        rx = [rx_by_seq.get(s) for s in sent_ok
              if lo <= ts_by_seq.get(s, -1) < hi and rx_by_seq.get(s)]
        if rx:
            out.append(round((max(rx) - hi) / 1000.0, 1))
    return {"mttr_s": max(out) if out else None, "mttr_per_cut_s": out}


def cmd_verify(a) -> int:
    meta_path = os.path.join(a.outdir, f"{a.run_id}-meta.json")
    log_path = os.path.join(a.outdir, f"{a.run_id}-sent.jsonl")
    if not os.path.exists(meta_path):
        print(f"{meta_path} олдсонгүй — эхлээд publish хийнэ үү", file=sys.stderr)
        return 2

    meta = json.load(open(meta_path, encoding="utf-8"))
    sent_rows = [json.loads(l) for l in open(log_path, encoding="utf-8")]
    sent_ok = [r["seq"] for r in sent_rows if r["published"]]
    ts_by_seq = {r["seq"]: r["ts"] for r in sent_rows}

    print(f"→ {a.run_id}: {len(sent_ok)} мессеж илгээгдсэн. "
          f"Өгөгдлийн сангаас хайж байна…", file=sys.stderr)

    rx_by_seq: dict[int, int | None] = {}
    if a.influx2:
        got = query_influx2(a.influx, a.org, a.bucket, a.token, a.run_id)
    else:
        rx_by_seq = query_influx3(a.influx, a.db, a.run_id, a.auth_token)
        got = set(rx_by_seq)

    lost = [s for s in sent_ok if s not in got]
    gaps = find_gaps(sent_ok, got)

    via = meta.get("via", sent_rows[0].get("via", "тодорхойгүй") if sent_rows else "тодорхойгүй")

    print(f"\n{'═'*66}\n  ӨГӨГДЛИЙН БҮРЭН БҮТЭН БАЙДАЛ — {a.run_id}\n{'═'*66}")
    print(f"  Зам (--via)           : {via}"
          + (f" — {VIA_LABEL[via]}" if via in VIA_LABEL else ""))
    print(f"  Илгээсэн (амжилттай)  : {len(sent_ok)}")
    print(f"  Сан дотор олдсон      : {len(got & set(sent_ok))}")
    print(f"  АЛДАГДСАН             : {len(lost)}  "
          f"({100*len(lost)/max(len(sent_ok),1):.2f}%)")
    print(f"  Илгээх үед амжилтгүй  : {meta['publish_failed']}")
    print(f"  Холболтын тасалдал    : {meta['disconnects']}")
    print(f"  Дахин холболт         : {meta['reconnects']}")

    if gaps:
        print(f"\n  {len(gaps)} тасалдлын хэсэг:")
        print(f"  {'#':>3} {'эхлэл seq':>10} {'төгсгөл':>9} {'урт':>7} "
              f"{'үргэлжлэл (с)':>14}")
        for i, (s, e) in enumerate(gaps, 1):
            dur = (ts_by_seq.get(e, 0) - ts_by_seq.get(s, 0)) / 1000
            print(f"  {i:>3} {s:>10} {e:>9} {e-s+1:>7} {dur:>14.1f}")
        longest = max(gaps, key=lambda g: g[1] - g[0])
        dur = (ts_by_seq.get(longest[1], 0) - ts_by_seq.get(longest[0], 0)) / 1000
        print(f"\n  Хамгийн урт тасалдал: {longest[1]-longest[0]+1} мессеж, "
              f"{dur:.1f} секунд")
    else:
        print("\n  ✓ Тасалдал илрээгүй — бүх мессеж хүрсэн.")

    # ── Гүүрний төлөвөөр хуваасан тайлан (--bridge-log өгөгдсөн бол) ──
    bridge_result: dict = {}
    if a.bridge_log:
        if not os.path.exists(a.bridge_log):
            print(f"\n  ⚠ --bridge-log олдсонгүй: {a.bridge_log} — алгаслаа",
                  file=sys.stderr)
        else:
            with open(a.bridge_log, encoding="utf-8") as bf:
                events = parse_bridge_events(bf)
            if not events:
                print(f"\n  ⚠ {a.bridge_log} дотор танигдах bridge/state мөр алга "
                      f"— алгаслаа", file=sys.stderr)
            else:
                last_ts = max(ts_by_seq.values()) if ts_by_seq else None
                down = bridge_down_intervals(events, end_ms=last_ts)
                bridge_result = report_bridge_split(sent_ok, lost, ts_by_seq, down)
    elif via == "edge" and not a.cut_log:
        print("\n  Санамж: --bridge-log өгвөл алдагдлыг гүүр унасан/ажилласан "
              "үеэр нь ХУВААЖ харуулна.")

    # ── Бодит өгсөх урсгалын тасалдлаар хуваах + MTTR (--cut-log) ──
    cut_result: dict = {}
    if a.cut_log:
        if not os.path.exists(a.cut_log):
            print(f"\n  ⚠ --cut-log олдсонгүй: {a.cut_log} — алгаслаа",
                  file=sys.stderr)
        else:
            with open(a.cut_log, encoding="utf-8") as cf:
                cevents = parse_bridge_events(cf)
            last_ts = max(ts_by_seq.values()) if ts_by_seq else None
            cdown = bridge_down_intervals(cevents, end_ms=last_ts)
            cut_result = report_bridge_split(
                sent_ok, lost, ts_by_seq, cdown,
                title="БОДИТ ӨГСӨХ УРСГАЛ (UPLINK)ИЙН ТАСАЛДЛААР ХУВААСАН АЛДАГДАЛ", key="cut")
            if rx_by_seq and any(v for v in rx_by_seq.values()):
                cut_result.update(mttr_after_cuts(sent_ok, rx_by_seq,
                                                  ts_by_seq, cdown))
                print(f"  MTTR (тасалдал дууссанаас хоцорсон сүүлийн мессеж "
                      f"санд хүрэх хүртэл): {cut_result['mttr_s']} сек")
            else:
                print("  MTTR: санд rx_ms талбар алга (Node-RED урсгалын "
                      "integrity салааг шалга) — гараар тооц.")

    result = {"run_id": a.run_id, "via": via, "sent_ok": len(sent_ok),
              "stored": len(got & set(sent_ok)), "lost": len(lost),
              "loss_pct": round(100*len(lost)/max(len(sent_ok), 1), 3),
              "gaps": [{"from": s, "to": e, "count": e-s+1,
                        "seconds": round((ts_by_seq.get(e, 0)
                                          - ts_by_seq.get(s, 0))/1000, 1)}
                       for s, e in gaps],
              **bridge_result, **cut_result,
              **{k: meta[k] for k in ("disconnects", "reconnects",
                                      "publish_failed", "qos")}}
    outp = os.path.join(a.outdir, f"{a.run_id}-result.json")
    json.dump(result, open(outp, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n  JSON: {outp}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Өгөгдлийн бүрэн бүтэн байдлын хэмжилт")
    sub = p.add_subparsers(dest="cmd", required=True)

    pub = sub.add_parser("publish")
    pub.add_argument("--via", choices=["edge", "direct"], default="direct",
                     help=("аль замаар илгээж байгааг тэмдэглэнэ (JSONL болон "
                           "meta-д бичигдэнэ). edge = Pi-гийн mosquitto → гүүр "
                           "→ EMQX (store-and-forward-ыг хэмжинэ); "
                           "direct = EMQX рүү шууд. Анхдагч: direct"))
    pub.add_argument("--host", default="localhost")
    pub.add_argument("--port", type=int, default=1883)
    pub.add_argument("--rate", type=float, default=10, help="мессеж/сек")
    pub.add_argument("--seconds", type=float, default=300)
    pub.add_argument("--qos", type=int, default=1, choices=[0, 1, 2])
    pub.add_argument("--run-id", required=True)
    pub.add_argument("--outdir", default="lab05/out")

    ver = sub.add_parser("verify")
    ver.add_argument("--influx", default="http://localhost:8181")
    ver.add_argument("--db", default="cnc302")
    ver.add_argument("--run-id", required=True)
    ver.add_argument("--outdir", default="lab05/out")
    ver.add_argument("--bridge-log", default=None,
                     help=("гүүрний төлөвийн JSONL файл ({\"ts\":…,\"state\":0|1}). "
                           "Өгвөл алдагдлыг гүүр УНАСАН ба АЖИЛЛАЖ байсан үеэр "
                           "нь тусад нь тайлагнана. Бичиж авах нь:  "
                           "mosquitto_sub -h localhost "
                           "-F '{\"ts\":%%U,\"state\":%%p}' "
                           "-t 'cnc302/shutis/mhts/lab/pi3b-01/bridge/state' "
                           "> lab05/out/bridge.jsonl"))
    ver.add_argument("--cut-log", default=None,
                     help=("failure_inject.sh-ийн бичсэн бодит тасалдлын JSONL "
                           "(lab05/out/uplink-events.jsonl). Алдагдлыг бодит "
                           "тасалдлаар хувааж, MTTR-ыг тооцно."))
    ver.add_argument("--auth-token",
                     default=os.getenv("INFLUXDB3_AUTH_TOKEN"),
                     help=("InfluxDB 3 токен (Authorization: Bearer). "
                           "--without-auth үед шаардлагагүй."))
    ver.add_argument("--influx2", action="store_true",
                     help="InfluxDB 2.7 нөөц хувилбар ашиглаж байгаа бол")
    ver.add_argument("--org", default="cnc302")
    ver.add_argument("--bucket", default="telemetry")
    ver.add_argument("--token", default="cnc302-lab-token")

    a = p.parse_args()
    return cmd_publish(a) if a.cmd == "publish" else cmd_verify(a)


if __name__ == "__main__":
    sys.exit(main())
