#!/usr/bin/env python3
"""
CNC302 Лаб 6 — Edge Impulse-д зориулж мэдрэгчийн өгөгдөл цуглуулах

X долоо хоногийн БИЕ ДААЛТААР ажиллуулна (лабораторийн цагаар биш).

MQTT-ээс өгөгдөл сонсож, Edge Impulse Studio-д шууд байршуулж болох
CSV файл болгон бичнэ. Edge Impulse-ийн CSV формат:
    timestamp,<axis1>,<axis2>,...

  # Хэвийн ажиллагааны өгөгдөл (3 минут)
  python3 collect_data.py --host pi-team03.local --label normal --seconds 180

  # Гажилтай өгөгдөл (sim_device.py-г --anomaly-rate 1.0-оор ажиллуул)
  python3 collect_data.py --host pi-team03.local --label anomaly --seconds 60
"""
from __future__ import annotations
import argparse, csv, json, os, sys, time
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

AXES = ["temperature", "humidity", "vibration_rms"]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--topic", default="cnc302/+/+/+/+/telemetry")
    p.add_argument("--label", required=True, help="ангиллын шошго (normal|anomaly|…)")
    p.add_argument("--seconds", type=float, default=180)
    p.add_argument("--device", help="зөвхөн энэ төхөөрөмжөөс")
    p.add_argument("--outdir", default="lab06/data")
    a = p.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(a.outdir, f"{a.label}-{stamp}.csv")
    rows: list[list] = []
    t0 = None

    def on_message(cl, u, m):
        nonlocal t0
        try:
            d = json.loads(m.payload)
        except Exception:
            return
        if a.device and d.get("device_id") != a.device:
            return
        ts = d.get("ts", int(time.time() * 1000))
        if t0 is None:
            t0 = ts
        rows.append([ts - t0] + [d.get(k, 0) for k in AXES])

    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"collect-{a.label}",
                    protocol=mqtt.MQTTv5)
    c.on_message = on_message
    c.connect(a.host, a.port, 30)
    c.subscribe(a.topic, qos=1)
    c.loop_start()
    print(f"→ '{a.label}' шошготой өгөгдөл {a.seconds:.0f} сек цуглуулж байна…",
          file=sys.stderr)
    end = time.time() + a.seconds
    while time.time() < end:
        time.sleep(2)
        print(f"  {len(rows)} дээж", end="\r", file=sys.stderr)
    c.loop_stop(); c.disconnect()

    if not rows:
        print("\nӨгөгдөл ирсэнгүй. sim_device.py ажиллаж байна уу?", file=sys.stderr)
        return 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp"] + AXES)
        w.writerows(rows)

    span = (rows[-1][0] - rows[0][0]) / 1000
    print(f"\n→ {len(rows)} дээж, {span:.1f} сек, "
          f"дундаж давтамж {len(rows)/max(span,1):.1f} Гц")
    print(f"→ {path}")
    print("\nEdge Impulse Studio → Data acquisition → Upload data →")
    print(f"  файл: {path}   шошго: {a.label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
