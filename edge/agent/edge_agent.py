#!/usr/bin/env python3
"""
CNC302 — ИРМЭГИЙН АГЕНТ (Raspberry Pi 3B).

Үүрэг:
  1. Pi-гийн БОДИТ хэмжүүрийг унших (температур, ачаалал, санах ой, throttle)
  2. Процессын дохиог үүсгэх (гадаад мэдрэгч байхгүй тохиолдолд)
  3. Unified Namespace сэдэвт ирмэгийн брокер руу нийтлэх
  4. Birth/death (LWT) төлөвийг зарлах
  5. Лаб 6-д: TFLite загвараар ЛОКАЛ дүгнэлт хийж, зөвхөн онцгой
     тохиолдлыг үүл рүү илгээх (ирмэгийн шүүлт)

Яагаад Pi-гийн бодит хэмжүүр вэ:
  Pi 3B-д мэдрэгч байхгүй ч CPU температур, ачаалал, санах ой нь
  БОДИТ, ХЭМЖИГДЭХҮЙЦ, ӨӨРЧЛӨГДДӨГ дохио. `stress-ng` ажиллуулбал
  температур бодитоор өснө — оюутан гараар аномали үүсгэж чадна.

Хэрэглээ:
    python3 edge_agent.py                    # .env-ийн утгаар
    python3 edge_agent.py --dry-run          # брокергүй, зөвхөн хэвлэнэ
    python3 edge_agent.py --once             # нэг удаа
    python3 edge_agent.py --detector ../lab06/models/anomaly_int8.tflite
    python3 edge_agent.py --filter           # зөвхөн аномалийг үүл рүү
"""
from __future__ import annotations

import argparse
import json
import os
import random
import signal
import socket
import sys
import time
import zlib
from pathlib import Path

try:
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion
    HAVE_MQTT = True
except ImportError:                                   # --dry-run горимд шаардлагагүй
    HAVE_MQTT = False

RUNNING = True


# ═══════════════════════════════════════════════════════════════════════════
#  1. Pi-гийн бодит хэмжүүр
# ═══════════════════════════════════════════════════════════════════════════

def _read_first_line(path: str) -> str | None:
    try:
        with open(path) as f:
            return f.readline().strip()
    except OSError:
        return None


def cpu_temp_c() -> float | None:
    """CPU температур (°C). Pi дээр thermal_zone0."""
    raw = _read_first_line("/sys/class/thermal/thermal_zone0/temp")
    if raw is None:
        return None
    try:
        v = float(raw)
    except ValueError:
        return None
    return round(v / 1000.0, 2) if v > 1000 else round(v, 2)


def load_avg() -> tuple[float, float, float]:
    try:
        return os.getloadavg()
    except OSError:
        return (0.0, 0.0, 0.0)


def mem_info() -> dict:
    """/proc/meminfo → MiB. Pi 3B-д нийт ~925 MiB харагдана."""
    out = {"mem_total_mb": None, "mem_available_mb": None, "swap_used_mb": None}
    try:
        vals = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, rest = line.partition(":")
                vals[k] = int(rest.strip().split()[0])          # kB
    except OSError:
        return out
    out["mem_total_mb"] = round(vals.get("MemTotal", 0) / 1024, 1)
    out["mem_available_mb"] = round(vals.get("MemAvailable", 0) / 1024, 1)
    swap_total = vals.get("SwapTotal", 0)
    swap_free = vals.get("SwapFree", 0)
    out["swap_used_mb"] = round((swap_total - swap_free) / 1024, 1)
    return out


_prev_cpu: tuple[int, int] | None = None


def cpu_percent() -> float | None:
    """/proc/stat-аас хоёр дуудлагын хооронд CPU ачааллыг тооцно."""
    global _prev_cpu
    line = _read_first_line("/proc/stat")
    if not line or not line.startswith("cpu "):
        return None
    parts = [int(x) for x in line.split()[1:]]
    idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
    total = sum(parts)
    if _prev_cpu is None:
        _prev_cpu = (idle, total)
        return None
    d_idle, d_total = idle - _prev_cpu[0], total - _prev_cpu[1]
    _prev_cpu = (idle, total)
    if d_total <= 0:
        return None
    return round(100.0 * (1.0 - d_idle / d_total), 1)


def throttled() -> str | None:
    """
    vcgencmd get_throttled → 0x0 бол хэвийн.
    bit 0 = яг одоо хүчдэл дутуу, bit 1 = давтамж хязгаарлагдсан,
    bit 2 = яг одоо throttling, bit 16..18 = өмнө нь тохиолдсон.
    Хэмжилтийн үнэн зөвд ЧУХАЛ — throttling эхэлмэгц бүх саатал гажина.
    """
    import subprocess
    try:
        r = subprocess.run(["vcgencmd", "get_throttled"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and "=" in r.stdout:
            return r.stdout.strip().split("=", 1)[1]
    except (OSError, subprocess.SubprocessError):
        pass
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  2. Процессын дохио (мэдрэгчийг орлоно)
# ═══════════════════════════════════════════════════════════════════════════

class ProcessSignal:
    """
    Үйлдвэрийн мотор/шугамын дохиог дуурайна:
      • удаан дрейф (өдрийн мөчлөг)
      • хэвийн шуугиан
      • санамсаргүй аномали (--anomaly-rate)

    Үр дүн нь ДАВТАГДАХУЙЦ: device_id-аар seed хийсэн тул нэг Pi үргэлж
    ижил цуваа өгнө — Лаб 6-д загварыг харьцуулахад зайлшгүй.
    """

    def __init__(self, device_id: str, anomaly_rate: float = 0.02):
        # ⚠ Python-ы built-in hash() нь мөрөнд ажиллах бүрт өөр утга өгдөг
        #   (PYTHONHASHSEED). Тиймээс тогтвортой crc32 ашиглана — эс бөгөөс
        #   "давтагдахуйц цуваа" гэдэг амлалт худал болно.
        self.rng = random.Random(zlib.crc32(device_id.encode()) & 0xFFFFFFFF)
        self.t = 0.0
        self.anomaly_rate = anomaly_rate
        self.base_temp = 62.0 + self.rng.uniform(-3, 3)
        self.base_vib = 0.42 + self.rng.uniform(-0.05, 0.05)

    def sample(self) -> dict:
        import math
        self.t += 1.0
        drift = 2.5 * math.sin(self.t / 240.0)
        temp = self.base_temp + drift + self.rng.gauss(0, 0.45)
        vib = self.base_vib + 0.03 * math.sin(self.t / 55.0) + self.rng.gauss(0, 0.012)
        rpm = 1480 + 12 * math.sin(self.t / 90.0) + self.rng.gauss(0, 4)
        anomaly = False
        if self.rng.random() < self.anomaly_rate:
            anomaly = True
            temp += self.rng.uniform(8, 18)
            vib += self.rng.uniform(0.20, 0.55)
            rpm -= self.rng.uniform(40, 130)
        return {
            "proc_temp_c": round(temp, 2),
            "vibration_g": round(vib, 4),
            "rpm": round(rpm, 1),
            "_injected_anomaly": anomaly,      # зөвхөн үнэлгээнд, үүл рүү явахгүй
        }


# ═══════════════════════════════════════════════════════════════════════════
#  3. Лаб 6 — локал дүгнэлт (сонголтот)
# ═══════════════════════════════════════════════════════════════════════════

class Detector:
    """
    TFLite загварыг ачаалж, нэг цонхны дүгнэлт хийнэ.
    Загвар байхгүй бол ЭНГИЙН босго ашиглана — Лаб 1–5-д энэ хангалттай.
    """

    def __init__(self, model_path: str | None, threads: int = 2):
        self.interp = None
        self.threshold = 0.6
        self.n = 0
        self.total_ms = 0.0
        if not model_path or not Path(model_path).exists():
            return
        try:
            try:
                from ai_edge_litert.interpreter import Interpreter
            except ImportError:
                from tflite_runtime.interpreter import Interpreter   # type: ignore
            self.interp = Interpreter(model_path=model_path, num_threads=threads)
            self.interp.allocate_tensors()
            self.inp = self.interp.get_input_details()[0]
            self.out = self.interp.get_output_details()[0]
            print(f"[detector] загвар ачаалагдлаа: {model_path} "
                  f"(оролт {self.inp['shape']}, {self.inp['dtype'].__name__})")
        except Exception as e:                       # noqa: BLE001
            print(f"[detector] ачаалж чадсангүй ({e}) — босгын горимд шилжлээ")
            self.interp = None

    def score(self, s: dict) -> tuple[float, float]:
        """(оноо 0..1, дүгнэлтийн хугацаа мс)"""
        t0 = time.perf_counter()
        if self.interp is None:
            # Босгын горим: хэвийн 62 °C / 0.42 g-ээс хазайлт
            dev = max(abs(s["proc_temp_c"] - 62.0) / 20.0,
                      abs(s["vibration_g"] - 0.42) / 0.6)
            score = min(1.0, max(0.0, dev))
        else:
            import numpy as np
            x = np.array([[s["proc_temp_c"], s["vibration_g"], s["rpm"]]],
                         dtype=np.float32)
            if self.inp["dtype"].__name__ == "int8":
                sc, zp = self.inp["quantization"]
                x = np.clip(np.round(x / sc + zp), -128, 127).astype(np.int8)
            self.interp.set_tensor(self.inp["index"], x)
            self.interp.invoke()
            y = self.interp.get_tensor(self.out["index"])
            if self.out["dtype"].__name__ == "int8":
                sc, zp = self.out["quantization"]
                y = (y.astype(np.float32) - zp) * sc
            score = float(np.clip(y.ravel()[0], 0.0, 1.0))
        ms = (time.perf_counter() - t0) * 1000.0
        self.n += 1
        self.total_ms += ms
        return score, ms

    @property
    def avg_ms(self) -> float:
        return self.total_ms / self.n if self.n else 0.0


# ═══════════════════════════════════════════════════════════════════════════
#  4. Агент
# ═══════════════════════════════════════════════════════════════════════════

def build_topics(site, area, line, dev) -> dict:
    base = f"cnc302/{site}/{area}/{line}/{dev}"
    return {
        "base": base,
        "telemetry": f"{base}/telemetry",
        "health": f"{base}/health",
        "status": f"{base}/status",
        "anomaly": f"{base}/anomaly",
        "cmd": f"{base}/cmd",
    }


def make_client(args, topics):
    if not HAVE_MQTT:
        sys.exit("paho-mqtt суулгаагүй байна:  pip install paho-mqtt")
    cid = f"edge-agent-{args.device_id}-{os.getpid()}"
    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=cid,
                    protocol=mqtt.MQTTv5)
    # LWT: агент унавал брокер энэ мессежийг өөрөө нийтэлнэ
    c.will_set(topics["status"],
               json.dumps({"online": False, "reason": "lwt"}),
               qos=1, retain=True)

    def on_connect(client, ud, flags, rc, props=None):
        if rc == 0:
            print(f"[mqtt] холбогдлоо {args.host}:{args.port}  (id={cid})")
            client.publish(topics["status"], json.dumps({
                "online": True, "agent": "cnc302-edge-agent/1.0",
                "host": socket.gethostname(), "ts": int(time.time() * 1000),
            }), qos=1, retain=True)
            client.subscribe(topics["cmd"], qos=1)
        else:
            print(f"[mqtt] холбогдож чадсангүй: rc={rc}")

    def on_message(client, ud, msg):
        print(f"[cmd] {msg.topic}  {msg.payload[:200]!r}")

    c.on_connect = on_connect
    c.on_message = on_message
    return c


def main() -> int:
    p = argparse.ArgumentParser(description="CNC302 ирмэгийн агент")
    p.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    p.add_argument("--site", default=os.getenv("SITE", "shutis"))
    p.add_argument("--area", default=os.getenv("AREA", "mhts"))
    p.add_argument("--line", default=os.getenv("LINE", "lab"))
    p.add_argument("--device-id", default=os.getenv("DEVICE_ID", socket.gethostname()))
    p.add_argument("--interval", type=float, default=float(os.getenv("INTERVAL", "2.0")))
    p.add_argument("--qos", type=int, default=1, choices=[0, 1, 2])
    p.add_argument("--count", type=int, default=0, help="0 = хязгааргүй")
    p.add_argument("--once", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="брокергүйгээр хэвлэнэ")
    p.add_argument("--anomaly-rate", type=float, default=0.02)
    p.add_argument("--detector", default=os.getenv("MODEL_PATH", ""))
    p.add_argument("--threads", type=int, default=int(os.getenv("INFER_THREADS", "2")))
    p.add_argument("--filter", action="store_true",
                   help="зөвхөн аномали + 30 сек тутмын хураангуйг илгээнэ "
                        "(ирмэгийн шүүлт — Лаб 6)")
    p.add_argument("--health-every", type=int, default=15,
                   help="хэдэн мөчлөг тутам Pi-гийн эрүүл мэндийг илгээх")
    args = p.parse_args()

    topics = build_topics(args.site, args.area, args.line, args.device_id)
    sig = ProcessSignal(args.device_id, args.anomaly_rate)
    det = Detector(args.detector or None, args.threads)

    print(f"UNS суурь : {topics['base']}")
    print(f"үе        : {args.interval} сек,  QoS {args.qos}"
          f"{',  ШҮҮЛТТЭЙ' if args.filter else ''}")

    client = None
    if not args.dry_run:
        client = make_client(args, topics)
        client.connect(args.host, args.port, keepalive=30)
        client.loop_start()

    global RUNNING
    signal.signal(signal.SIGINT, lambda *_: globals().__setitem__("RUNNING", False))
    signal.signal(signal.SIGTERM, lambda *_: globals().__setitem__("RUNNING", False))

    n = sent = suppressed = 0
    limit = 1 if args.once else args.count
    t_start = time.time()

    while RUNNING:
        n += 1
        s = sig.sample()
        injected = s.pop("_injected_anomaly")
        score, ms = det.score(s)
        is_anom = score >= det.threshold

        payload = {
            "ts": int(time.time() * 1000),
            "device": args.device_id,
            "seq": n,
            **s,
            "score": round(score, 4),
            "anomaly": is_anom,
            "infer_ms": round(ms, 3),
        }

        # Шүүлттэй горимд: аномали + үе үе "би амьд байна" хураангуй.
        # Хураангуйгүй бол үүл нь чимээгүй ирмэгийг үхсэнээс ялгаж чадахгүй.
        send = (not args.filter) or is_anom or (n % args.health_every == 0)
        if send:
            sent += 1
            if args.dry_run:
                print(json.dumps(payload, ensure_ascii=False))
            else:
                client.publish(topics["telemetry"], json.dumps(payload),
                               qos=args.qos)
                if is_anom:
                    client.publish(topics["anomaly"], json.dumps(payload), qos=1)
        else:
            suppressed += 1

        # Pi-гийн эрүүл мэнд — Лаб 1, 4, 5-д Grafana дээр хардаг
        if n % args.health_every == 0:
            h = {
                "ts": int(time.time() * 1000),
                "device": args.device_id,
                "cpu_temp_c": cpu_temp_c(),
                "cpu_pct": cpu_percent(),
                "load1": round(load_avg()[0], 2),
                "throttled": throttled(),
                "uptime_s": int(time.time() - t_start),
                "sent": sent,
                "suppressed": suppressed,
                "infer_avg_ms": round(det.avg_ms, 3),
                **mem_info(),
            }
            if args.dry_run:
                print(json.dumps(h, ensure_ascii=False))
            else:
                client.publish(topics["health"], json.dumps(h), qos=0)

        if injected and is_anom is False:
            print(f"  ! {n}: аномали оруулсан ч илрээгүй (score={score:.3f})")

        if limit and n >= limit:
            break
        time.sleep(args.interval)

    print(f"\nилгээсэн {sent}, дарсан {suppressed}, "
          f"дүгнэлт дундаж {det.avg_ms:.2f} мс")

    if client is not None:
        client.publish(topics["status"],
                       json.dumps({"online": False, "reason": "shutdown"}),
                       qos=1, retain=True)
        time.sleep(0.4)
        client.loop_stop()
        client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
