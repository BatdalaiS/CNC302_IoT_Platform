#!/usr/bin/env python3
"""
CNC302 Лаб 6 — Ирмэгийн дүгнэлтийн гүйцэтгэлийг хэмжих (Raspberry Pi 3B)

Лабораторийн гол хэрэгсэл. Загварын НАРИЙВЧЛАЛ биш, БАЙРШУУЛАЛТЫН ӨРТӨГ-ийг
хэмжинэ: саатал, санах ой, CPU, дулаан.

⚠ ХУРДАСГУУР БАЙХГҮЙ. Pi 3B-д PCIe байхгүй тул Raspberry Pi AI Kit
  (Hailo-8L) ФИЗИКИЙН ХУВЬД холбогдох боломжгүй. Тиймээс энэ хэрэгсэлд
  hailo backend БАЙХГҮЙ (AI Kit нь Raspberry Pi 5-ын PCIe-д зориулагдсан).
  Бүх хэмжилт BCM2837, 4 цөмт 1.2 ГГц CPU дээр хийгдэнэ.

⚠ MobileNet-ийн зэрэглэлийн зурган загвар Pi 3B дээр ЗОРИУДААР хэт удаан.
  Хэдэн зуун мс, бүр секунд гарна — энэ нь алдаа биш, ХЭМЖИХ ЁСТОЙ БАРИМТ.
  "Хэр удаан вэ, яагаад вэ" гэдгийг тоогоор нотлох нь даалгаврын нэг хэсэг.
  Харин БОДИТООР байршуулах загвар бол жижиг ХҮСНЭГТ/ЦОНХНЫ гажил илрүүлэгч
  (3–5 оролт, хэдэн KiB) — edge/agent/edge_agent.py яг түүнийг ачаална.

Дэмжигдэх backend:
  tflite      LiteRT (хуучин нэр TensorFlow Lite) (.tflite) — CPU
              pip: ai-edge-litert  (шинэ; cp311 aarch64 wheel бий)
                   tflite-runtime  (хуучин; сүүлийн хувилбар 2.14, 2023)
  eim         Edge Impulse Linux runner (.eim)       — CPU. Edge Impulse нь
              Pi 3-ыг албан ёсоор дэмждэг самбарын жагсаалтад ОРУУЛААГҮЙ
              (Pi 4/5 бий) — СОНГОЛТОТ, өөрийн эрсдэлээр.
  onnx        ONNX Runtime (.onnx)                   — CPU (pip: onnxruntime,
              Python ≥3.11, aarch64 wheel бий)
  synthetic   загваргүй суурь (аргачлалыг турших)    — хаана ч ажиллана

Хэмжилтийн үнэн зөвийн ГУРВАН НӨХЦӨЛ (Pi 3B дээр):
  1. ЗААВАЛ халаана. CPU-гийн давтамж сул үеийн доод утгаасаа 1.2 ГГц
     рүү өсөх, кэш дүүрэх хүртэл эхний дүгнэлтүүд удаан. --cold нь халаалтыг алгасна
     (зөвхөн "халаалт яагаад хэрэгтэй вэ" гэсэн туршилтад).
  2. `vcgencmd get_throttled`-ыг ӨМНӨ ба ДАРАА нь уншина. Өөрчлөгдвөл
     тухайн ажиллалт ХҮЧИНГҮЙ — throttling эхэлмэгц бүх саатал гажина.
  3. --threads анхдагчаар 2 (доорх тайлбарыг үз).

Жишээ:
  # Аргачлалыг турших (загваргүй)
  python3 benchmark_inference.py --backend synthetic --runs 500 --device-label pi3b

  # float32 ба int8 загварыг харьцуулах
  python3 benchmark_inference.py --backend tflite --model models/model_float32.tflite --runs 300
  python3 benchmark_inference.py --backend tflite --model models/model_int8.tflite --runs 300

  # Edge Impulse-ийн байршуулсан загвар
  python3 benchmark_inference.py --backend eim --model models/anomaly.eim --runs 300

  # НЭГ ХҮСНЭГТ: Pi 3B CPU / зөөврийн компьютерийн CPU / багшийн лавлах мөр
  python3 benchmark_inference.py --backend synthetic --device-label pi3b \\
      --label synth-t2 --csv lab06/out/bench.csv        # Pi 3B дээр
  python3 benchmark_inference.py --backend synthetic --device-label laptop-cpu \\
      --label synth-t2 --csv lab06/out/bench.csv        # зөөврийн компьютер дээр
  # → нэг CSV, device_label баганаар нь ялгана
"""
from __future__ import annotations

import argparse
import csv
import gc
import json
import os
import statistics
import subprocess
import sys
import time

import numpy as np

# Халаалтын ЗААВАЛ байх доод хязгаар. --warmup үүнээс бага байсан ч
# энэ тоо руу өснө (--cold-оос бусад тохиолдолд).
MIN_WARMUP = 20
WARMUP_MAX = 5000


# ─────────────────────────── систем ба нөөц ───────────────────────────

def rss_mib() -> float:
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def cpu_times() -> float:
    t = os.times()
    return t.user + t.system


def read_temp() -> float:
    try:
        out = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True,
                             text=True, timeout=3).stdout
        return float(out.strip().split("=")[1].replace("'C", ""))
    except Exception:  # noqa: BLE001
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", encoding="utf-8") as f:
                return int(f.read()) / 1000
        except OSError:
            return 0.0


def model_size_kib(path: str | None) -> float:
    return os.path.getsize(path) / 1024 if path and os.path.exists(path) else 0.0


# ────────────────── Pi 3B: throttling-ийн хяналт ──────────────────
# Хэмжилтийн үнэн зөвд ХАМГИЙН чухал шалгалт. Хүчдэл дутах, эсвэл цөмийн
# температур 80–85 °C-д хүрэхэд Arm цөмүүд аажмаар, 85 °C-д Arm ба GPU
# хоёулаа удаашруулагдана (raspberrypi.com/documentation). Тэр мөчөөс хойшхи
# бүх саатал гажина. Битүүд: `vcgencmd get_throttled`-ийн албан ёсны хүснэгт.
# 3-р бит (зөөлөн дулааны хязгаар) нь Pi 3B+-ийн онцлог — Pi 3B дээр 0 байна.
THROTTLE_BITS = {
    0: "яг одоо хүчдэл дутуу байна",
    1: "яг одоо давтамж хязгаарлагдсан (arm_freq capped)",
    2: "яг одоо THROTTLING болж байна",
    3: "яг одоо зөөлөн дулааны хязгаар идэвхтэй",
    16: "ачаалснаас хойш хүчдэл дутсан",
    17: "ачаалснаас хойш давтамж хязгаарлагдсан",
    18: "ачаалснаас хойш throttling болсон",
    19: "ачаалснаас хойш зөөлөн дулааны хязгаарт хүрсэн",
}


def throttled_hex() -> str | None:
    """
    `vcgencmd get_throttled` → '0x0' бол бүх зүйл хэвийн.
    Pi биш (эсвэл vcgencmd байхгүй) бол None буцаана — тэр тохиолдолд
    шалгалт зүгээр л алгасагдана.
    """
    try:
        r = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True,
                           text=True, timeout=3)
        if r.returncode == 0 and "=" in r.stdout:
            return r.stdout.strip().split("=", 1)[1]
    except Exception:  # noqa: BLE001
        pass
    return None


def throttle_reasons(value: str | None) -> list[str]:
    """0x50005 гэх мэт утгыг монголоор тайлбарлана."""
    if not value:
        return []
    try:
        v = int(value, 16)
    except ValueError:
        return []
    return [t for bit, t in THROTTLE_BITS.items() if v & (1 << bit)]


# ─────────────────────────── backend-ууд ───────────────────────────

class Backend:
    name = "base"

    def __init__(self, args) -> None:
        self.args = args
        self.input_shape: tuple = (1, args.window)

    def infer(self, x: np.ndarray):
        raise NotImplementedError

    def describe(self) -> dict:
        return {"backend": self.name}


class Synthetic(Backend):
    """
    Загваргүй суурь: жижиг матрицын үржвэр. Бодит загвар байхгүй үед
    аргачлалыг турших, мөн 'дүгнэлтийн доод хязгаар'-ыг тогтооход хэрэгтэй.
    """
    name = "synthetic"

    def __init__(self, args) -> None:
        super().__init__(args)
        rng = np.random.default_rng(42)
        n = args.window
        self.w1 = rng.standard_normal((n, 64)).astype(np.float32)
        self.w2 = rng.standard_normal((64, 32)).astype(np.float32)
        self.w3 = rng.standard_normal((32, 1)).astype(np.float32)

    def infer(self, x: np.ndarray):
        h = np.maximum(x @ self.w1, 0)
        h = np.maximum(h @ self.w2, 0)
        return h @ self.w3

    def describe(self) -> dict:
        params = self.w1.size + self.w2.size + self.w3.size
        return {"backend": self.name, "params": params,
                "params_kib": round(params * 4 / 1024, 1)}


class TFLite(Backend):
    name = "tflite"

    def __init__(self, args) -> None:
        super().__init__(args)
        interp_cls = None
        for mod, attr in (("ai_edge_litert.interpreter", "Interpreter"),
                          ("tflite_runtime.interpreter", "Interpreter"),
                          ("tensorflow.lite", "Interpreter")):
            try:
                m = __import__(mod, fromlist=[attr])
                interp_cls = getattr(m, attr)
                self.lib = mod
                break
            except Exception:  # noqa: BLE001
                continue
        if interp_cls is None:
            raise RuntimeError(
                "TFLite орчин олдсонгүй. Суулгах:\n"
                "  pip install ai-edge-litert      # шинэ нэр\n"
                "  pip install tflite-runtime      # хуучин нэр")
        self.it = interp_cls(model_path=args.model, num_threads=args.threads)
        self.it.allocate_tensors()
        self.inp = self.it.get_input_details()[0]
        self.out = self.it.get_output_details()[0]
        self.input_shape = tuple(int(d) for d in self.inp["shape"])

    def infer(self, x: np.ndarray):
        # Бүрэн int8 загварт оролтыг квантчилна: q = round(x / scale) + zero_point
        # (scale, zero_point нь get_input_details()[0]["quantization"]-д).
        d = self.inp["dtype"]
        if d in (np.int8, np.uint8):
            scale, zp = self.inp["quantization"]
            info = np.iinfo(d)
            x = np.clip(np.round(x / (scale or 1.0)) + zp, info.min, info.max).astype(d)
        else:
            x = x.astype(d)
        self.it.set_tensor(self.inp["index"], x.reshape(self.inp["shape"]))
        self.it.invoke()
        y = self.it.get_tensor(self.out["index"])
        # Гаралтыг буцааж бодит тоо болгоно: y = (q - zero_point) * scale
        if self.out["dtype"] in (np.int8, np.uint8):
            scale, zp = self.out["quantization"]
            y = (y.astype(np.float32) - zp) * (scale or 1.0)
        return y

    def describe(self) -> dict:
        return {"backend": self.name, "lib": self.lib,
                "input_dtype": str(self.inp["dtype"].__name__),
                "output_dtype": str(self.out["dtype"].__name__),
                "quantized": self.inp["dtype"] in (np.int8, np.uint8),
                "threads": self.args.threads}


class EdgeImpulse(Backend):
    name = "eim"

    def __init__(self, args) -> None:
        super().__init__(args)
        try:
            from edge_impulse_linux.runner import ImpulseRunner
        except ImportError as exc:
            raise RuntimeError(
                "edge_impulse_linux олдсонгүй. Суулгах:\n"
                "  pip install edge_impulse_linux") from exc
        self.runner = ImpulseRunner(args.model)
        self.info = self.runner.init()
        import atexit
        atexit.register(self.runner.stop)      # .eim дэд процессыг хаана
        self.window = self.info["model_parameters"].get("input_features_count",
                                                        args.window)
        self.input_shape = (1, self.window)

    def infer(self, x: np.ndarray):
        return self.runner.classify(x.flatten().tolist())

    def describe(self) -> dict:
        p = self.info.get("model_parameters", {})
        return {"backend": self.name,
                "project": self.info.get("project", {}).get("name", ""),
                "features": p.get("input_features_count"),
                "sensor": p.get("sensor"),
                "labels": ",".join(p.get("labels", []))}


class ONNX(Backend):
    name = "onnx"

    def __init__(self, args) -> None:
        super().__init__(args)
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError("pip install onnxruntime") from exc
        so = ort.SessionOptions()
        so.intra_op_num_threads = args.threads
        self.sess = ort.InferenceSession(args.model, so,
                                         providers=["CPUExecutionProvider"])
        self.iname = self.sess.get_inputs()[0].name
        self.input_shape = tuple(
            d if isinstance(d, int) else 1
            for d in self.sess.get_inputs()[0].shape)

    def infer(self, x: np.ndarray):
        return self.sess.run(None, {self.iname: x.reshape(self.input_shape)
                                    .astype(np.float32)})

    def describe(self) -> dict:
        return {"backend": self.name, "providers": self.sess.get_providers(),
                "threads": self.args.threads}


BACKENDS = {"synthetic": Synthetic, "tflite": TFLite,
            "eim": EdgeImpulse, "onnx": ONNX}


# ─────────────────────────── хэмжилт ───────────────────────────

def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    k = min(int(round(p / 100 * (len(sorted_vals) - 1))), len(sorted_vals) - 1)
    return sorted_vals[k]


def benchmark(be: Backend, a) -> dict:
    rng = np.random.default_rng(0)
    shape = be.input_shape
    sample = rng.standard_normal(shape).astype(np.float32)

    gc.collect()
    mem_before = rss_mib()
    temp_before = read_temp()
    thr_before = throttled_hex()

    # ЗААВАЛ ХАЛААХ. Pi 3B дээр эхний дуудлагууд ямагт удаан: кэш хоосон,
    # санах ой хуваарилагдаагүй, ondemand governor давтамжийг 600 МГц-ээс
    # 1.2 ГГц рүү өсгөж амжаагүй байдаг. Халаалтгүй хэмжилтийн p99 нь
    # загварын биш, эхлэлийн өртгийг хэмждэг.
    warm = 0 if a.cold else max(a.warmup, MIN_WARMUP)
    t_warm0 = time.perf_counter()
    for _ in range(warm):
        be.infer(sample)
    # Хугацааны доод хязгаар: удаан загварт дүгнэлтийн тоо хангалттай, харин
    # хурдан загварт governor 1.2 ГГц хүртэл өсөх хугацаа хэрэгтэй. WARMUP_MAX
    # нь маш хурдан машин дээр халаалт хэдэн зуун мянга болохоос сэргийлнэ.
    while (not a.cold and warm < WARMUP_MAX
           and (time.perf_counter() - t_warm0) < a.warmup_seconds):
        be.infer(sample)
        warm += 1

    gc.collect()
    mem_after_warm = rss_mib()

    lat: list[float] = []
    cpu0 = cpu_times()
    t0 = time.perf_counter()
    for _ in range(a.runs):
        x = rng.standard_normal(shape).astype(np.float32)
        s = time.perf_counter()
        be.infer(x)
        lat.append((time.perf_counter() - s) * 1000)
    wall = time.perf_counter() - t0
    cpu_used = cpu_times() - cpu0

    gc.collect()
    mem_peak = rss_mib()
    temp_after = read_temp()
    thr_after = throttled_hex()
    lat.sort()

    return {
        "label": a.label or be.name,
        "device_label": a.device_label,      # pi3b | laptop-cpu | reference …
        "backend": be.name,
        "model": os.path.basename(a.model) if a.model else "",
        "model_kib": round(model_size_kib(a.model), 1),
        "runs": a.runs,
        "warmup_done": warm,
        "threads": a.threads,
        "lat_p50_ms": round(percentile(lat, 50), 3),
        "lat_p95_ms": round(percentile(lat, 95), 3),
        "lat_p99_ms": round(percentile(lat, 99), 3),
        "lat_min_ms": round(lat[0], 3),
        "lat_max_ms": round(lat[-1], 3),
        "lat_mean_ms": round(statistics.fmean(lat), 3),
        "lat_stdev_ms": round(statistics.pstdev(lat), 3),
        "throughput_infer_s": round(a.runs / wall, 1),
        "cpu_ms_per_infer": round(cpu_used * 1000 / a.runs, 3),
        "cpu_efficiency": round(cpu_used / wall, 3),
        "mem_before_mib": round(mem_before, 1),
        "mem_after_warmup_mib": round(mem_after_warm, 1),
        "mem_peak_mib": round(mem_peak, 1),
        "mem_model_mib": round(mem_after_warm - mem_before, 1),
        "temp_before_c": temp_before,
        "temp_after_c": temp_after,
        "temp_delta_c": round(temp_after - temp_before, 1),
        "throttled_before": thr_before or "n/a",
        "throttled_after": thr_after or "n/a",
        "throttled_changed": bool(thr_before and thr_after
                                  and thr_before != thr_after),
    }


def warn_throttled(r: dict) -> None:
    """
    Throttling нь хэмжилтийг ХҮЧИНГҮЙ болгоно. Чимээгүй өнгөрөөвөл оюутан
    гажсан тоог тайландаа бичнэ — тиймээс энд ЧАНГА анхааруулна.
    """
    if r["throttled_before"] == "n/a":
        return                       # Pi биш — шалгалт байхгүй
    if r["throttled_changed"]:
        print(f"\n{'!'*64}")
        print("  ⚠⚠ АНХААР: АЖИЛЛАЛТЫН ЯВЦАД THROTTLING ТОХИОЛДЛОО!")
        print(f"  vcgencmd get_throttled:  {r['throttled_before']}"
              f"  →  {r['throttled_after']}")
        for t in throttle_reasons(r["throttled_after"]):
            print(f"    · {t}")
        print("  ЭНЭ ХЭМЖИЛТ ХҮЧИНГҮЙ. Тайланд бүү оруул. Хийх зүйл:")
        print("    1. Pi-г хөргөж (радиатор/сэнс), 5 минут амраа")
        print("    2. Тэжээлийг шалга — 5V/2.5A эх үүсвэр ЗААВАЛ "
              "(USB порт, сул кабель болохгүй)")
        print("    3. vcgencmd get_throttled нь 0x0 болсны дараа дахин ажиллуул")
        print(f"{'!'*64}")
    elif throttle_reasons(r["throttled_before"]):
        print("\n  ⚠ Санамж: ажиллалт эхлэхээс ӨМНӨ throttling-ийн тэмдэглэгээ "
              f"байсан ({r['throttled_before']}):")
        for t in throttle_reasons(r["throttled_before"]):
            print(f"      · {t}")
        print("    Ажиллалтын явцад өөрчлөгдөөгүй тул тоог ашиглаж болно, "
              "гэхдээ шалтгааныг тайландаа тэмдэглэ.")


def print_result(r: dict, info: dict) -> None:
    print(f"\n{'═'*64}\n  {r['label']}  ({r['backend']} @ {r['device_label']})"
          f"\n{'═'*64}")
    for k, v in info.items():
        print(f"  {k:<22} {v}")
    print(f"  {'-'*60}")
    rows = [
        ("Төхөөрөмж", r["device_label"]),
        ("Халаалт", f"{r['warmup_done']} дүгнэлт"),
        ("Загварын хэмжээ", f"{r['model_kib']:.1f} KiB"),
        ("Санах ой (загвар)", f"{r['mem_model_mib']:.1f} MiB"),
        ("Санах ой (оргил)", f"{r['mem_peak_mib']:.1f} MiB"),
        ("Саатал p50", f"{r['lat_p50_ms']:.3f} мс"),
        ("Саатал p95", f"{r['lat_p95_ms']:.3f} мс"),
        ("Саатал p99", f"{r['lat_p99_ms']:.3f} мс"),
        ("Саатал min / max", f"{r['lat_min_ms']:.3f} / {r['lat_max_ms']:.3f} мс"),
        ("Тогтвортой байдал (σ)", f"{r['lat_stdev_ms']:.3f} мс"),
        ("Чадвар", f"{r['throughput_infer_s']:.1f} дүгнэлт/с"),
        ("CPU нэг дүгнэлтэд", f"{r['cpu_ms_per_infer']:.3f} мс"),
        ("CPU ашиглалт", f"{r['cpu_efficiency']:.2f} цөм"),
        ("Температур", f"{r['temp_before_c']:.1f} → {r['temp_after_c']:.1f} °C"),
        ("Throttle (өмнө → дараа)",
         f"{r['throttled_before']} → {r['throttled_after']}"),
    ]
    for k, v in rows:
        print(f"  {k:<24} {v:>28}")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Ирмэгийн дүгнэлтийн гүйцэтгэлийн хэмжилт",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--backend", choices=list(BACKENDS), default="synthetic")
    p.add_argument("--model", help=".tflite / .eim / .onnx файл")
    p.add_argument("--runs", type=int, default=300)
    p.add_argument("--warmup", type=int, default=30,
                   help=f"халаалтын дүгнэлтийн тоо (доод хязгаар {MIN_WARMUP})")
    p.add_argument("--warmup-seconds", type=float, default=2.0,
                   help="халаалтын доод ХУГАЦАА, сек (governor 1.2 ГГц хүрэх)")
    p.add_argument("--cold", action="store_true",
                   help="халаалтыг БҮРЭН алгасах — зөвхөн 'халаалт яагаад "
                        "хэрэгтэй вэ' туршилтад. Тоо нь хүчингүй.")
    # Pi 3B-д 4 цөм бий ч --threads 4 нь ихэвчлэн 2-оос УДААН гардаг:
    # A53 цөмүүд нэг л санах ойн сувгийг (LPDDR2, ~1.6 GB/s) хуваалцдаг тул
    # 4 урсгал зурвасын өргөнд түгжигдээд, дээрээс нь дулаан нэмэгдэж
    # throttling-ийг хурдасгана. Тиймээс анхдагч нь 2 — 1/2/4-ийг ӨӨРӨӨ хэмж.
    p.add_argument("--threads", type=int, default=2,
                   help="CPU урсгалын тоо (Pi 3B: 1 vs 2 vs 4-ийг харьцуул!)")
    p.add_argument("--window", type=int, default=125,
                   help="synthetic backend-ийн оролтын урт")
    p.add_argument("--label", help="CSV дэх мөрийн шошго")
    p.add_argument("--device-label", default="unknown",
                   help="ямар төмөр дээр хэмжив: pi3b | laptop-cpu | reference "
                        "— CSV-д хадгалагдаж нэг хүснэгтэд харьцуулагдана")
    p.add_argument("--csv", help="үр дүнг CSV-д НЭМЖ бичих")
    p.add_argument("--json", help="үр дүнг JSON-д бичих")
    a = p.parse_args()

    if a.backend != "synthetic" and not a.model:
        print("--model заавал шаардлагатай", file=sys.stderr)
        return 2

    try:
        be = BACKENDS[a.backend](a)
    except RuntimeError as exc:
        print(f"\n{exc}\n", file=sys.stderr)
        print("Санамж: --backend synthetic ашиглаж аргачлалыг турших боломжтой.",
              file=sys.stderr)
        return 3

    info = be.describe()
    warm_txt = "ХАЛААЛТГҮЙ (--cold)" if a.cold else \
        f"{max(a.warmup, MIN_WARMUP)}+ халаалт / ≥{a.warmup_seconds:.1f} сек"
    print(f"→ {a.backend} @ {a.device_label}: {a.runs} дүгнэлт ({warm_txt}), "
          f"оролт={be.input_shape}, урсгал={a.threads}", file=sys.stderr)
    if a.cold:
        print("  ⚠ --cold: халаалтгүй тоо нь ЗӨВХӨН харьцуулалтад, "
              "тайлангийн үндсэн хүснэгтэд бүү оруул.", file=sys.stderr)
    r = benchmark(be, a)
    print_result(r, info)
    warn_throttled(r)

    if a.csv:
        os.makedirs(os.path.dirname(a.csv) or ".", exist_ok=True)
        new = not os.path.exists(a.csv)
        with open(a.csv, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(r.keys()))
            if new:
                w.writeheader()
            w.writerow(r)
        print(f"\n  CSV → {a.csv}")
    if a.json:
        json.dump({**r, **info}, open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print(f"  JSON → {a.json}")

    # Бодит цагийн шаардлагад нийцэж байна уу?
    print(f"\n  Санамж: 100 Гц мэдрэгчид дүгнэлт 10 мс-ээс бага байх ёстой. "
          f"Таных: p99 = {r['lat_p99_ms']:.2f} мс → "
          f"{'НИЙЦЭЖ БАЙНА' if r['lat_p99_ms'] < 10 else 'НИЙЦЭХГҮЙ'}")
    print("  Харьцуулалт: ижил --label-тай мөрийг pi3b ба laptop-cpu дээр "
          "авч, CSV-гээ нэг хүснэгт болго.")
    # throttling гарсан бол алдааны кодоор буцна — оюутан анзаарахгүй өнгөрөхгүй
    return 4 if r["throttled_changed"] else 0


if __name__ == "__main__":
    sys.exit(main())
