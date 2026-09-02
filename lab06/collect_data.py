#!/usr/bin/env python3
"""
CNC302 Лаб 6 — Сургалтын өгөгдөл цуглуулах (ирмэгийн брокерээс)

X долоо хоногийн БИЕ ДААЛТААР ажиллуулна (лабораторийн цагаар биш).

Хаанаас сонсох вэ:
  Энэ скрипт RASPBERRY PI 3B дээр, ИРМЭГИЙН брокероос (localhost:1883)
  сонсоно. Үүлэн дэх EMQX-ээс биш — учир нь гүүр тасарсан ч ирмэгийн
  өгөгдөл үргэлжилнэ, мөн сургалтын өгөгдөлд гүүрний саатал нэмэгдэхгүй.
  Хэрэв зөөврийн компьютер дээрээсээ цуглуулмаар бол:
      python3 collect_data.py --host <pi-ийн-IP> …

Ямар өгөгдөл вэ:
  edge/agent/edge_agent.py нь UNS-ийн `telemetry` суваг руу дараах
  талбартай JSON нийтэлдэг:
      ts, device, seq, proc_temp_c, vibration_g, rpm, score, anomaly, infer_ms
  Анхдагч тэнхлэгүүд нь эдгээрээс ГУРАВ: proc_temp_c, vibration_g, rpm.
  (tools/sim_device.py-ийн хуучин талбарууд хэрэгтэй бол:
      --axes temperature,humidity,vibration_rms)

Гаралт нь Edge Impulse Studio-д шууд байршуулж болох CSV:
      timestamp,<тэнхлэг1>,<тэнхлэг2>,…

  # Хэвийн ажиллагааны өгөгдөл (Pi дээр, агент ажиллаж байхад)
  python3 collect_data.py --label normal --seconds 300

  # Гажилтай өгөгдөл (агентыг --anomaly-rate 1.0-оор ажиллуул)
  python3 collect_data.py --label anomaly --seconds 120

  # Зөвхөн нэг төхөөрөмжөөс, тодорхой UNS салбараас
  python3 collect_data.py --label normal --device pi3b-01 --site shutis
"""
from __future__ import annotations
import argparse, csv, json, os, sys, time
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

# Ирмэгийн агентын телеметрийн үндсэн тэнхлэгүүд
DEFAULT_AXES = "proc_temp_c,vibration_g,rpm"


def main() -> int:
    p = argparse.ArgumentParser(
        description="Сургалтын өгөгдлийг ирмэгийн брокероос цуглуулах",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    # Анхдагч нь Pi дээрх ИРМЭГИЙН mosquitto
    p.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    p.add_argument("--site", default=os.getenv("SITE", "shutis"))
    p.add_argument("--area", default=os.getenv("AREA", "mhts"))
    p.add_argument("--line", default=os.getenv("LINE", "lab"))
    p.add_argument("--device", help="зөвхөн энэ төхөөрөмжөөс (ж: pi3b-01)")
    p.add_argument("--topic", help="сэдвийг гараар заах (UNS-ээс давуу)")
    p.add_argument("--axes", default=DEFAULT_AXES,
                   help=f"CSV-д бичих талбарууд (анхдагч: {DEFAULT_AXES})")
    p.add_argument("--label", required=True, help="ангиллын шошго (normal|anomaly|…)")
    p.add_argument("--seconds", type=float, default=180)
    p.add_argument("--outdir", default="lab06/data")
    a = p.parse_args()

    axes = [x.strip() for x in a.axes.split(",") if x.strip()]
    # UNS: cnc302/<site>/<area>/<line>/<device>/<channel>
    topic = a.topic or (f"cnc302/{a.site}/{a.area}/{a.line}/"
                        f"{a.device or '+'}/telemetry")

    os.makedirs(a.outdir, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = os.path.join(a.outdir, f"{a.label}-{stamp}.csv")
    rows: list[list] = []
    seen_keys: set[str] = set()
    devices: set[str] = set()
    t0 = None

    def on_message(cl, u, m):
        nonlocal t0
        try:
            d = json.loads(m.payload)
        except Exception:
            return
        # Төхөөрөмжийн нэр: агент 'device', хуучин симулятор 'device_id'
        dev = d.get("device") or d.get("device_id") or m.topic.split("/")[4]
        if a.device and dev != a.device:
            return
        seen_keys.update(d.keys())
        devices.add(str(dev))
        ts = d.get("ts", int(time.time() * 1000))
        if t0 is None:
            t0 = ts
        rows.append([ts - t0] + [d.get(k, 0) for k in axes])

    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"collect-{a.label}",
                    protocol=mqtt.MQTTv5)
    c.on_message = on_message
    c.connect(a.host, a.port, 30)
    c.subscribe(topic, qos=1)
    c.loop_start()
    print(f"→ брокер {a.host}:{a.port},  сэдэв {topic}", file=sys.stderr)
    print(f"→ '{a.label}' шошготой өгөгдөл {a.seconds:.0f} сек цуглуулж байна…",
          file=sys.stderr)
    end = time.time() + a.seconds
    while time.time() < end:
        time.sleep(2)
        print(f"  {len(rows)} дээж", end="\r", file=sys.stderr)
    c.loop_stop(); c.disconnect()

    if not rows:
        print("\nӨгөгдөл ирсэнгүй. Шалгах зүйлс:", file=sys.stderr)
        print("  1. Ирмэгийн агент ажиллаж байна уу? "
              "(cd edge && make agent)", file=sys.stderr)
        print("  2. mosquitto асаалттай юу? (docker compose ps)", file=sys.stderr)
        print(f"  3. Сэдэв таарч байна уу? "
              f"mosquitto_sub -h {a.host} -t '{topic}' -C 1", file=sys.stderr)
        return 1

    missing = [k for k in axes if k not in seen_keys]
    if missing:
        print(f"\n⚠ Эдгээр талбар мессежид БАЙХГҮЙ тул 0-ээр бичигдэв: "
              f"{', '.join(missing)}", file=sys.stderr)
        print(f"  Мессежид байгаа талбарууд: {', '.join(sorted(seen_keys))}",
              file=sys.stderr)
        print("  --axes-ээ зөв утгаар дахин ажиллуул.", file=sys.stderr)

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp"] + axes)
        w.writerows(rows)

    span = (rows[-1][0] - rows[0][0]) / 1000
    print(f"\n→ {len(rows)} дээж, {span:.1f} сек, "
          f"дундаж давтамж {len(rows)/max(span,1):.1f} Гц")
    print(f"→ төхөөрөмж: {', '.join(sorted(devices))}")
    print(f"→ {path}")
    print("\nEdge Impulse Studio → Data acquisition → Upload data →")
    print(f"  файл: {path}   шошго: {a.label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
