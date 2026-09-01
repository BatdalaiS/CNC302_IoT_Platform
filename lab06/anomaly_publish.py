#!/usr/bin/env python3
"""
CNC302 Лаб 6 — Ирмэгийн дүгнэлтийг платформд буцаан нэгтгэх

Мэдрэгчийн урсгалыг сонсож, гулсах цонхонд загвар ажиллуулж, гажил илэрвэл
UNS-ийн `event` суваг руу нийтэлнэ. Ингэснээр Лаб 5-ын Rule Engine, Grafana
дохиолол ирмэгийн AI-тай холбогдоно.

  python3 anomaly_publish.py --host pi-team03.local --backend synthetic
  python3 anomaly_publish.py --host pi-team03.local --backend tflite \
      --model lab06/models/model_int8.tflite --threshold 0.7
"""
from __future__ import annotations
import argparse, json, sys, time
from collections import defaultdict, deque

import numpy as np
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from benchmark_inference import BACKENDS  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--backend", choices=list(BACKENDS), default="synthetic")
    p.add_argument("--model")
    p.add_argument("--window", type=int, default=125)
    p.add_argument("--threads", type=int, default=1)
    p.add_argument("--threshold", type=float, default=0.8)
    p.add_argument("--seconds", type=float, default=0, help="0 = хязгааргүй")
    a = p.parse_args()

    be = BACKENDS[a.backend](a)
    buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=a.window))
    stats = {"in": 0, "infer": 0, "alerts": 0, "lat_sum": 0.0}

    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="edge-ai",
                    protocol=mqtt.MQTTv5)

    def on_message(cl, u, m):
        try:
            d = json.loads(m.payload)
        except Exception:
            return
        stats["in"] += 1
        parts = m.topic.split("/")
        if len(parts) != 6:
            return
        dev = parts[4]
        buffers[dev].append(float(d.get("vibration_rms", 0)))
        if len(buffers[dev]) < a.window:
            return

        x = np.array(buffers[dev], dtype=np.float32).reshape(be.input_shape)
        t0 = time.perf_counter()
        out = be.infer(x)
        lat = (time.perf_counter() - t0) * 1000
        stats["infer"] += 1
        stats["lat_sum"] += lat

        score = float(np.max(np.asarray(out, dtype=np.float32)))
        score = 1 / (1 + np.exp(-score / 10))     # 0..1 руу шахна
        if score >= a.threshold:
            stats["alerts"] += 1
            evt = {"ts": int(time.time() * 1000), "device_id": dev,
                   "type": "anomaly", "score": round(score, 4),
                   "inference_ms": round(lat, 3), "source": "edge-ai",
                   "backend": be.name}
            cl.publish("/".join(parts[:5] + ["event"]),
                       json.dumps(evt), qos=1)
            print(f"  ⚠ {dev} гажил score={score:.3f} ({lat:.2f} мс)")

    c.on_message = on_message
    c.connect(a.host, a.port, 30)
    c.subscribe("cnc302/+/+/+/+/telemetry", qos=1)
    c.loop_start()
    print(f"→ Ирмэгийн дүгнэлт ажиллаж байна ({be.name}, "
          f"цонх={a.window}, босго={a.threshold})…")

    t_end = time.time() + a.seconds if a.seconds else float("inf")
    try:
        last = 0
        while time.time() < t_end:
            time.sleep(10)
            n = stats["infer"]
            avg = stats["lat_sum"] / n if n else 0
            print(f"  ирсэн={stats['in']:<7} дүгнэлт={n:<7} "
                  f"дохиолол={stats['alerts']:<5} дундаж саатал={avg:.2f} мс "
                  f"({(n-last)/10:.1f} дүгнэлт/с)")
            last = n
    except KeyboardInterrupt:
        pass
    c.loop_stop(); c.disconnect()
    n = stats["infer"]
    print(f"\nДүн: {stats['in']} мессеж, {n} дүгнэлт, "
          f"{stats['alerts']} дохиолол, дундаж "
          f"{stats['lat_sum']/max(n,1):.2f} мс")
    return 0


if __name__ == "__main__":
    sys.exit(main())
