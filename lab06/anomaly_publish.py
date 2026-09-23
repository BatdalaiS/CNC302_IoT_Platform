#!/usr/bin/env python3
"""
CNC302 Лаб 6 — Ирмэгийн дүгнэлтийг UNS рүү буцаан нэгтгэх

Ирмэгийн брокерын телеметрийг сонсож, гулсах цонхонд загвар ажиллуулж,
гажил илэрвэл UNS-ийн `anomaly` суваг руу нийтэлнэ. Гүүр (bridge) тэр
мессежийг үүл рүү дамжуулах тул Лаб 5-ын Node-RED шугам, Grafana
дохиолол ирмэгийн AI-тай холбогдоно.

Хаана ажиллах вэ:
  Raspberry Pi 3B дээр, ИРМЭГИЙН mosquitto-той (localhost:1883). Ингэснээр
  үүл унасан ч гажил илрүүлэлт үргэлжилнэ — ирмэгийн тооцооллын гол утга
  учир нь яг энэ.

Хоёр горим (загварын оролтын хэмжээгээр АВТОМАТААР сонгоно):
  • ВЕКТОР — загварын оролт = --fields-ийн тоо (train_tiny_model.py-ийн
    [1,3] загвар): мессеж бүрээс proc_temp_c, vibration_g, rpm-ийг авч
    ШУУД дүгнэнэ. Гаралт = гажлын магадлал 0..1.
  • ЦОНХ — бусад тохиолдолд: --field талбарын сүүлийн N утгыг (N = загварын
    оролтын хэмжээ, synthetic үед --window) цонх болгож дүгнэнэ.

  # Pi дээр (агент ажиллаж байх ёстой)
  python3 anomaly_publish.py --backend synthetic
  python3 anomaly_publish.py --backend tflite \
      --model lab06/models/model_int8.tflite --threshold 0.7

  # Зөөврийн компьютерээс Pi-гийн брокер руу
  python3 anomaly_publish.py --host <pi-ийн-IP> --backend synthetic
"""
from __future__ import annotations
import argparse, json, os, sys, time
from collections import defaultdict, deque

import numpy as np
import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from benchmark_inference import BACKENDS  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(
        description="Ирмэгийн гажил илрүүлэлт → UNS anomaly суваг")
    # Анхдагч нь Pi дээрх ИРМЭГИЙН брокер
    p.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    p.add_argument("--site", default=os.getenv("SITE", "shutis"))
    p.add_argument("--area", default=os.getenv("AREA", "mhts"))
    p.add_argument("--line", default=os.getenv("LINE", "lab"))
    p.add_argument("--device", help="зөвхөн энэ төхөөрөмжийг сонсох (ж: pi3b-01)")
    p.add_argument("--field", default="vibration_g",
                   help="ЦОНХ горимд хуримтлуулах талбар "
                        "(агент: vibration_g | proc_temp_c | rpm)")
    p.add_argument("--fields", default="proc_temp_c,vibration_g,rpm",
                   help="ВЕКТОР горимын оролтын талбарууд (дараалал нь "
                        "сургалтынхтай ИЖИЛ байх ёстой)")
    p.add_argument("--backend", choices=list(BACKENDS), default="synthetic")
    p.add_argument("--model")
    p.add_argument("--window", type=int, default=125)
    # Pi 3B: 4 цөм бий ч 2 урсгал ихэвчлэн илүү тогтвортой (санах ойн зурвас)
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--threshold", type=float, default=0.8)
    p.add_argument("--seconds", type=float, default=0, help="0 = хязгааргүй")
    a = p.parse_args()

    be = BACKENDS[a.backend](a)
    fields = [f.strip() for f in a.fields.split(",") if f.strip()]
    n_in = int(np.prod(be.input_shape))
    vector_mode = a.backend != "synthetic" and n_in == len(fields)
    window = 1 if vector_mode else n_in
    # UNS: cnc302/<site>/<area>/<line>/<device>/<channel>
    sub_topic = (f"cnc302/{a.site}/{a.area}/{a.line}/"
                 f"{a.device or '+'}/telemetry")
    buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=window))
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
        if vector_mode:
            if any(not isinstance(d.get(k), (int, float)) for k in fields):
                return                      # шаардлагатай талбар дутуу
            x = np.array([d[k] for k in fields], dtype=np.float32)
        else:
            buffers[dev].append(float(d.get(a.field, 0)))
            if len(buffers[dev]) < window:
                return
            x = np.array(buffers[dev], dtype=np.float32)
        x = x.reshape(be.input_shape)
        t0 = time.perf_counter()
        out = be.infer(x)
        lat = (time.perf_counter() - t0) * 1000
        stats["infer"] += 1
        stats["lat_sum"] += lat

        raw = float(np.max(np.asarray(out, dtype=np.float32)))
        if be.name == "synthetic":
            # санамсаргүй жинтэй сүлжээ — зөвхөн аргачлалыг турших зорилготой
            score = float(1 / (1 + np.exp(-raw / 10)))
        else:
            # сигмоид гаралттай загвар: аль хэдийн 0..1 (int8 бол benchmark_
            # inference.TFLite.infer() буцааж бодит тоо болгосон)
            score = min(1.0, max(0.0, raw))
        if score >= a.threshold:
            stats["alerts"] += 1
            evt = {"ts": int(time.time() * 1000), "device": dev,
                   "type": "anomaly", "score": round(score, 4),
                   "input": ",".join(fields) if vector_mode else a.field,
                   "window": window,
                   "inference_ms": round(lat, 3), "source": "edge-ai",
                   "backend": be.name}
            # UNS-ийн anomaly суваг → гүүрээр үүл рүү (out чиглэл)
            cl.publish("/".join(parts[:5] + ["anomaly"]),
                       json.dumps(evt), qos=1)
            print(f"  ⚠ {dev} гажил score={score:.3f} ({lat:.2f} мс)")

    c.on_message = on_message
    c.connect(a.host, a.port, 30)
    c.subscribe(sub_topic, qos=1)
    c.loop_start()
    print(f"→ брокер {a.host}:{a.port},  сэдэв {sub_topic}")
    mode = (f"ВЕКТОР {fields}" if vector_mode
            else f"ЦОНХ талбар={a.field}, урт={window}")
    print(f"→ Ирмэгийн дүгнэлт ажиллаж байна ({be.name}, {mode}, "
          f"урсгал={a.threads}, босго={a.threshold})…")

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
