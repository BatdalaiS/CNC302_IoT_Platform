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

Жишээ:
  # 1-р терминал: 5 минут, секундэд 10 мессеж
  python data_integrity.py publish --host pi-team03.local \\
      --rate 10 --seconds 300 --run-id run1

  # 2-р терминал: энэ хооронд эвдрэл үүсгэнэ
  bash failure_inject.sh broker 30

  # Дараа нь шалгана
  python data_integrity.py verify --influx http://pi-team03.local:8181 \\
      --run-id run1
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

TOPIC = "cnc302/ulaanbaatar/campus/line01/integrity/telemetry"
MEASUREMENT = "integrity"


# ────────────────────────────── PUBLISH ──────────────────────────────

def cmd_publish(a) -> int:
    os.makedirs(a.outdir, exist_ok=True)
    logpath = os.path.join(a.outdir, f"{a.run_id}-sent.jsonl")

    sent = 0
    failed = 0
    disconnects = 0
    reconnects = 0
    connected = {"v": False}

    def on_connect(cl, u, f, rc, p=None):
        if rc == 0:
            if connected["v"]:
                pass
            connected["v"] = True

    def on_disconnect(cl, u, flags, rc, p=None):
        nonlocal disconnects
        connected["v"] = False
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
            log.write(json.dumps({**payload, "published": ok}) + "\n")

            if sent % (a.rate * 10) == 0 and sent:
                print(f"  [{time.strftime('%H:%M:%S')}] илгээв={sent} "
                      f"амжилтгүй={failed} тасалдал={disconnects}",
                      file=sys.stderr)
            time.sleep(interval)

    c.loop_stop()
    c.disconnect()

    meta = {"run_id": a.run_id, "topic": TOPIC, "qos": a.qos,
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

def query_influx3(base: str, db: str, run_id: str) -> set[int]:
    r = requests.post(
        f"{base.rstrip('/')}/api/v3/query_sql",
        json={"db": db,
              "q": f"SELECT seq FROM {MEASUREMENT} WHERE run_id = '{run_id}'",
              "format": "json"},
        timeout=60,
    )
    r.raise_for_status()
    return {int(row["seq"]) for row in r.json() if row.get("seq") is not None}


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

    if a.influx2:
        got = query_influx2(a.influx, a.org, a.bucket, a.token, a.run_id)
    else:
        got = query_influx3(a.influx, a.db, a.run_id)

    lost = [s for s in sent_ok if s not in got]
    gaps = find_gaps(sent_ok, got)

    print(f"\n{'═'*66}\n  ӨГӨГДЛИЙН БҮРЭН БҮТЭН БАЙДАЛ — {a.run_id}\n{'═'*66}")
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

    result = {"run_id": a.run_id, "sent_ok": len(sent_ok),
              "stored": len(got & set(sent_ok)), "lost": len(lost),
              "loss_pct": round(100*len(lost)/max(len(sent_ok), 1), 3),
              "gaps": [{"from": s, "to": e, "count": e-s+1,
                        "seconds": round((ts_by_seq.get(e, 0)
                                          - ts_by_seq.get(s, 0))/1000, 1)}
                       for s, e in gaps],
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
    ver.add_argument("--influx2", action="store_true",
                     help="InfluxDB 2.7 нөөц хувилбар ашиглаж байгаа бол")
    ver.add_argument("--org", default="cnc302")
    ver.add_argument("--bucket", default="telemetry")
    ver.add_argument("--token", default="cnc302-lab-token")

    a = p.parse_args()
    return cmd_publish(a) if a.cmd == "publish" else cmd_verify(a)


if __name__ == "__main__":
    sys.exit(main())
