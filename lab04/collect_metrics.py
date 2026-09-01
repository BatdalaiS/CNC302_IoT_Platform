#!/usr/bin/env python3
"""
CNC302 Лаб 4 — Ачааллын тестийн үеийн үзүүлэлтийг цуглуулах

Raspberry Pi ДЭЭР ажиллана. Ачааллын тест явж байх зуур дараах зүйлийг
тогтмол давтамжтайгаар бичнэ:

  · EMQX     — холболтын тоо, мессежийн хурд, дараалалд хүлээгч
  · Docker   — контейнер бүрийн CPU, санах ой
  · Систем   — ачаалал, сул санах ой, температур, throttle

Гаралт: measurements/loadtest-<шошго>-<огноо>.csv

Жишээ:
  python3 collect_metrics.py --label 100dev --seconds 180
  python3 collect_metrics.py --label ramp --seconds 900 --interval 5
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

import requests

FIELDS = [
    "ts", "elapsed_s", "label",
    "emqx_connections", "emqx_live_connections", "emqx_topics",
    "emqx_subscriptions", "emqx_msg_in_rate", "emqx_msg_out_rate",
    "emqx_msg_dropped", "emqx_retained",
    "cpu_emqx", "mem_emqx_mib", "cpu_thingsboard", "mem_thingsboard_mib",
    "cpu_influxdb", "mem_influxdb_mib", "cpu_total_pct",
    "load1", "mem_available_mib", "swap_used_mib",
    "temp_c", "throttled",
]


def emqx_metrics(base: str, user: str, password: str) -> dict:
    """EMQX 5.x REST API v5-ээс үзүүлэлт авна."""
    out = {k: "" for k in FIELDS if k.startswith("emqx_")}
    try:
        auth = (user, password)
        s = requests.get(f"{base}/api/v5/stats", auth=auth, timeout=4).json()
        stats = s[0] if isinstance(s, list) else s
        out["emqx_connections"] = stats.get("connections.count", "")
        out["emqx_live_connections"] = stats.get("live_connections.count", "")
        out["emqx_topics"] = stats.get("topics.count", "")
        out["emqx_subscriptions"] = stats.get("subscriptions.count", "")
        out["emqx_retained"] = stats.get("retained.count", "")

        m = requests.get(f"{base}/api/v5/metrics", auth=auth, timeout=4).json()
        met = m[0] if isinstance(m, list) else m
        out["emqx_msg_in_rate"] = met.get("messages.received", "")
        out["emqx_msg_out_rate"] = met.get("messages.sent", "")
        out["emqx_msg_dropped"] = met.get("messages.dropped", "")
    except Exception as exc:  # noqa: BLE001
        print(f"  EMQX API алдаа: {exc}", file=sys.stderr)
    return out


def docker_stats() -> dict:
    out: dict[str, str] = {}
    try:
        raw = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.Name}};{{.CPUPerc}};{{.MemUsage}}"],
            capture_output=True, text=True, timeout=25,
        ).stdout
    except Exception:  # noqa: BLE001
        return out

    total_cpu = 0.0
    for line in raw.strip().splitlines():
        try:
            name, cpu, mem = line.split(";")
        except ValueError:
            continue
        cpu_v = float(cpu.strip().rstrip("%") or 0)
        total_cpu += cpu_v
        mib = 0.0
        mm = re.match(r"([\d.]+)\s*([KMG]i?B)", mem.strip())
        if mm:
            v, unit = float(mm.group(1)), mm.group(2)
            mib = {"KiB": v / 1024, "MiB": v, "GiB": v * 1024,
                   "KB": v / 1024, "MB": v, "GB": v * 1024}.get(unit, v)
        short = name.replace("cnc302-", "")
        if short in ("emqx", "thingsboard", "influxdb"):
            out[f"cpu_{short}"] = round(cpu_v, 2)
            out[f"mem_{short}_mib"] = round(mib, 1)
    out["cpu_total_pct"] = round(total_cpu, 2)
    return out


def system_stats() -> dict:
    out: dict[str, str] = {}
    try:
        out["load1"] = round(os.getloadavg()[0], 2)
    except Exception:  # noqa: BLE001
        pass
    try:
        info = {}
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.strip().split()[0])
        out["mem_available_mib"] = round(info.get("MemAvailable", 0) / 1024, 1)
        out["swap_used_mib"] = round(
            (info.get("SwapTotal", 0) - info.get("SwapFree", 0)) / 1024, 1)
    except Exception:  # noqa: BLE001
        pass
    for key, cmd in (("temp_c", ["vcgencmd", "measure_temp"]),
                     ("throttled", ["vcgencmd", "get_throttled"])):
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
            out[key] = r.stdout.strip().split("=")[-1].replace("'C", "")
        except Exception:  # noqa: BLE001
            out[key] = ""
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Ачааллын тестийн үзүүлэлт цуглуулах")
    p.add_argument("--label", default="run", help="CSV-д бичих шошго")
    p.add_argument("--seconds", type=float, default=180)
    p.add_argument("--interval", type=float, default=5)
    p.add_argument("--emqx", default="http://localhost:18083")
    p.add_argument("--emqx-user", default="admin")
    p.add_argument("--emqx-password",
                   default=os.environ.get("EMQX_DASHBOARD_PASSWORD", "public"))
    p.add_argument("--outdir", default="measurements")
    a = p.parse_args()

    os.makedirs(a.outdir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(a.outdir, f"loadtest-{a.label}-{stamp}.csv")

    print(f"→ {a.seconds:.0f} сек, {a.interval:.0f} сек тутам → {path}")
    print(f"{'үлдсэн':>8} {'холболт':>9} {'мсж/с':>9} {'CPU%':>7} "
          f"{'сул MiB':>9} {'°C':>6}")

    t0 = time.time()
    prev_in, prev_t = None, None
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        while (elapsed := time.time() - t0) < a.seconds:
            row = {k: "" for k in FIELDS}
            row["ts"] = datetime.now(timezone.utc).isoformat()
            row["elapsed_s"] = round(elapsed, 1)
            row["label"] = a.label
            row.update(emqx_metrics(a.emqx, a.emqx_user, a.emqx_password))
            row.update(docker_stats())
            row.update(system_stats())

            # хуримтлагдсан тоолуураас хурдыг гаргана
            rate = ""
            cur_in = row.get("emqx_msg_in_rate")
            now = time.time()
            if prev_in not in (None, "") and cur_in not in (None, ""):
                try:
                    rate = round((int(cur_in) - int(prev_in)) / (now - prev_t), 1)
                except Exception:  # noqa: BLE001
                    rate = ""
            prev_in, prev_t = cur_in, now
            row["emqx_msg_out_rate"] = rate     # багана дахин ашиглав: бодит хурд

            w.writerow(row)
            f.flush()
            print(f"{a.seconds-elapsed:8.0f} {str(row['emqx_connections']):>9} "
                  f"{str(rate):>9} {str(row.get('cpu_total_pct','')):>7} "
                  f"{str(row.get('mem_available_mib','')):>9} "
                  f"{str(row.get('temp_c','')):>6}")
            time.sleep(a.interval)

    print(f"\n→ Бичигдлээ: {path}")
    print("  Дараа нь: python3 plot_scaling.py " + path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
