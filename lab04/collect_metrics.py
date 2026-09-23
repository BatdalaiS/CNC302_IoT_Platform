#!/usr/bin/env python3
"""
CNC302 Лаб 4 — Ачааллын тестийн үеийн үзүүлэлтийг цуглуулах

Стек хоёр хостод хуваагдсан тул энэ скриптийг ХОЁР ХОСТ ДЭЭР ТУСАД НЬ
ажиллуулж, дараа нь plot_scaling.py-гаар НЭГ ТЭНХЛЭГ ДЭЭР харьцуулна:

  --target edge    Raspberry Pi 3B дээр  → mosquitto, 1 GB RAM, 100 Mb/s Ethernet
  --target cloud   зөөврийн компьютер дээр → EMQX, InfluxDB, …

`target` багана CSV-д бичигдэх бөгөөд plot_scaling.py түүгээр нь ХОЁР МУРУЙГ
ялгана. Хоёр хостын CSV-г нэг дор өгч болно.

Хэмжиж буй БРОКЕРЫН үзүүлэлт (`broker_*` багана) зорилтоос хамаарна:

  · edge  → ирмэгийн mosquitto-гийн $SYS сэдвүүд (mosquitto(8)):
              $SYS/broker/clients/connected
              $SYS/broker/publish/messages/received   (PUBLISH-ийн нийт тоо)
              $SYS/broker/publish/messages/dropped
              $SYS/broker/store/messages/count        (messages/stored нь хуучирсан)
            $SYS нь sys_interval тутам (анхдагч 10 с) шинэчлэгдэнэ.
  · cloud → EMQX 5 REST API: /api/v5/stats, /api/v5/metrics (?aggregate=true)

EMQX REST API-д 5.0-оос хойш самбарын нэр/нууц үгээр Basic auth ХИЙХ
БОЛОМЖГҮЙ. Хоёр аргын нэгийг ашиглана:
  1) API түлхүүр: EMQX_API_KEY / EMQX_API_SECRET (stack/.env) → Basic auth
  2) эсвэл самбарын хэрэглэгч: POST /api/v5/login → Bearer token

Үүнээс гадна:
  · Docker   — контейнер бүрийн CPU, санах ой, санах ойн хязгаарын % (MemPerc)
  · Систем   — load, сул санах ой, swap in/out (/proc/vmstat pswpin/pswpout —
               `vmstat`-ын si/so-гийн эх), сүлжээний tx/rx Mbit/с
               (/sys/class/net/<iface>/statistics), температур, throttle

Гаралт: measurements/loadtest-<зорилт>-<шошго>-<огноо>.csv

Жишээ:
  # Pi 3B дээр (EMQX нь зөөврийн компьютер дээр — сонголттой)
  python3 collect_metrics.py --target edge --label ramp --seconds 900

  # Зөөврийн компьютер дээр
  python3 collect_metrics.py --target cloud --label ramp --seconds 900

⚠ Pi 3B дээр throttle нь 0x0 биш болвол, эсвэл сул RAM 150 MiB-ээс доош орвол
  тухайн мөрүүдийн саатал/чадварын тоо ХҮЧИНГҮЙ. Скрипт үүнийг анхааруулна.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

import requests

FIELDS = [
    "ts", "elapsed_s", "target", "label",
    # зорилтын брокер (edge = mosquitto $SYS, cloud = EMQX)
    "broker_connections", "broker_msg_in_rate", "broker_dropped_total",
    "broker_store_count",
    # EMQX-ийн түүхий тоолуур (cloud; edge дээр --emqx өгвөл үүлнийх)
    "emqx_connections", "emqx_live_connections", "emqx_topics",
    "emqx_subscriptions", "emqx_msg_received", "emqx_msg_sent",
    "emqx_msg_dropped", "emqx_retained",
    # Docker
    "cpu_emqx", "mem_emqx_mib", "mem_emqx_pct",
    "cpu_mosquitto", "mem_mosquitto_mib", "mem_mosquitto_pct",
    "cpu_influxdb", "mem_influxdb_mib", "mem_influxdb_pct", "cpu_total_pct",
    # систем
    "load1", "mem_available_mib", "swap_used_mib",
    "swap_in_pages_s", "swap_out_pages_s", "net_tx_mbit", "net_rx_mbit",
    "temp_c", "throttled",
]

TRACKED = ("emqx", "mosquitto", "influxdb")
EDGE_RAM_WARN_MIB = 150


# ─────────────────────────── EMQX REST API ───────────────────────────

class Emqx:
    """EMQX 5 REST API. API түлхүүр байвал Basic, эс бөгөөс /login → Bearer."""

    def __init__(self, base: str, key: str, secret: str, user: str, password: str):
        self.base = base.rstrip("/") + "/api/v5"
        self.key, self.secret = key, secret
        self.user, self.password = user, password
        self.token: str | None = None

    def _get(self, path: str):
        kw: dict = {"timeout": 4, "params": {"aggregate": "true"}}
        if self.key:
            kw["auth"] = (self.key, self.secret)
        else:
            if not self.token:
                r = requests.post(f"{self.base}/login", timeout=4,
                                  json={"username": self.user,
                                        "password": self.password})
                r.raise_for_status()
                self.token = r.json()["token"]
            kw["headers"] = {"Authorization": f"Bearer {self.token}"}
        r = requests.get(f"{self.base}{path}", **kw)
        if r.status_code == 401 and not self.key:
            self.token = None               # хугацаа дууссан token → дахин нэвтэрнэ
        r.raise_for_status()
        d = r.json()
        return d[0] if isinstance(d, list) else d

    def metrics(self) -> dict:
        out = {k: "" for k in FIELDS if k.startswith("emqx_")}
        try:
            st = self._get("/stats")
            out["emqx_connections"] = st.get("connections.count", "")
            out["emqx_live_connections"] = st.get("live_connections.count", "")
            out["emqx_topics"] = st.get("topics.count", "")
            out["emqx_subscriptions"] = st.get("subscriptions.count", "")
            out["emqx_retained"] = st.get("retained.count", "")
            me = self._get("/metrics")
            out["emqx_msg_received"] = me.get("messages.received", "")
            out["emqx_msg_sent"] = me.get("messages.sent", "")
            out["emqx_msg_dropped"] = me.get("messages.dropped", "")
        except Exception as exc:  # noqa: BLE001
            print(f"  EMQX API алдаа: {exc}", file=sys.stderr)
        return out


# ─────────────────────────── mosquitto $SYS ───────────────────────────

class MosquittoSys:
    """Ирмэгийн mosquitto-гийн $SYS сэдвүүдийг арын thread-д сонсоно."""

    TOPICS = {
        "$SYS/broker/clients/connected": "connected",
        "$SYS/broker/publish/messages/received": "pub_received",
        "$SYS/broker/publish/messages/dropped": "pub_dropped",
        "$SYS/broker/store/messages/count": "store_count",
    }

    def __init__(self, host: str, port: int, user: str | None, password: str | None):
        import paho.mqtt.client as mqtt
        from paho.mqtt.enums import CallbackAPIVersion
        self.lock = threading.Lock()
        self.vals: dict[str, float] = {}
        self.hist: list[tuple[float, float]] = []   # (цаг, pub_received)
        self.c = mqtt.Client(CallbackAPIVersion.VERSION2,
                             client_id=f"cnc302-collect-{os.getpid()}")
        if user:
            self.c.username_pw_set(user, password)
        self.c.on_connect = lambda cl, u, f, rc, p: [
            cl.subscribe(t, qos=0) for t in self.TOPICS]
        self.c.on_message = self._on_message
        self.c.connect(host, port, keepalive=30)
        self.c.loop_start()

    def _on_message(self, cl, u, m) -> None:
        key = self.TOPICS.get(m.topic)
        try:
            v = float(m.payload.decode())
        except ValueError:
            return
        with self.lock:
            self.vals[key] = v
            if key == "pub_received":
                self.hist.append((time.time(), v))
                self.hist = self.hist[-2:]

    def snapshot(self) -> dict:
        with self.lock:
            out = {"broker_connections": self.vals.get("connected", ""),
                   "broker_dropped_total": self.vals.get("pub_dropped", ""),
                   "broker_store_count": self.vals.get("store_count", ""),
                   "broker_msg_in_rate": ""}
            if len(self.hist) == 2 and self.hist[1][0] > self.hist[0][0]:
                (t0, v0), (t1, v1) = self.hist
                out["broker_msg_in_rate"] = round((v1 - v0) / (t1 - t0), 1)
        return out

    def close(self) -> None:
        self.c.disconnect()
        self.c.loop_stop()


# ─────────────────────────── Docker ба систем ───────────────────────────

def docker_stats() -> dict:
    out: dict[str, object] = {}
    try:
        raw = subprocess.run(
            ["docker", "stats", "--no-stream", "--format",
             "{{.Name}};{{.CPUPerc}};{{.MemUsage}};{{.MemPerc}}"],
            capture_output=True, text=True, timeout=25,
        ).stdout
    except Exception:  # noqa: BLE001
        return out

    total_cpu = 0.0
    for line in raw.strip().splitlines():
        try:
            name, cpu, mem, memperc = line.split(";")
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
        if short in TRACKED:
            out[f"cpu_{short}"] = round(cpu_v, 2)
            out[f"mem_{short}_mib"] = round(mib, 1)
            out[f"mem_{short}_pct"] = memperc.strip().rstrip("%")
    out["cpu_total_pct"] = round(total_cpu, 2)
    return out


def default_iface() -> str:
    """/proc/net/route-аас анхдагч чиглүүлэлтийн интерфейсийг олно."""
    try:
        with open("/proc/net/route", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                p = line.split()
                if len(p) > 1 and p[1] == "00000000":
                    return p[0]
    except OSError:
        pass
    return "eth0"


class Counters:
    """Хуримтлагдсан тоолуураас секунд тутмын хурд гаргана."""

    def __init__(self, iface: str):
        self.iface = iface
        self.prev: dict[str, float] = {}
        self.prev_t = 0.0

    def _read(self) -> dict[str, float]:
        v: dict[str, float] = {}
        try:
            with open("/proc/vmstat", encoding="utf-8") as f:
                for line in f:
                    k, n = line.split()
                    if k in ("pswpin", "pswpout"):
                        v[k] = float(n)
        except OSError:
            pass
        for k in ("tx_bytes", "rx_bytes"):
            try:
                with open(f"/sys/class/net/{self.iface}/statistics/{k}",
                          encoding="utf-8") as f:
                    v[k] = float(f.read())
            except OSError:
                pass
        return v

    def rates(self) -> dict:
        now, cur = time.time(), self._read()
        out: dict[str, object] = {}
        if self.prev:
            dt = max(now - self.prev_t, 1e-6)
            d = {k: (cur[k] - self.prev[k]) / dt for k in cur if k in self.prev}
            if "pswpin" in d:
                out["swap_in_pages_s"] = round(d["pswpin"], 1)
                out["swap_out_pages_s"] = round(d["pswpout"], 1)
            if "tx_bytes" in d:
                out["net_tx_mbit"] = round(d["tx_bytes"] * 8 / 1e6, 2)
                out["net_rx_mbit"] = round(d["rx_bytes"] * 8 / 1e6, 2)
        self.prev, self.prev_t = cur, now
        return out


def system_stats() -> dict:
    out: dict[str, object] = {}
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


def detect_target() -> str:
    """/proc/device-tree/model дотор 'Raspberry Pi' байвал ирмэг гэж үзнэ."""
    try:
        with open("/proc/device-tree/model", "rb") as f:
            if b"raspberry pi" in f.read().lower():
                return "edge"
    except OSError:
        pass
    return "cloud"


def main() -> int:
    p = argparse.ArgumentParser(description="Ачааллын тестийн үзүүлэлт цуглуулах")
    p.add_argument("--target", choices=["edge", "cloud"], default=None,
                   help=("аль хостыг хэмжиж байна вэ. CSV-ийн `target` баганад "
                         "бичигдэж, plot_scaling.py-д ХОЁР МУРУЙГ ялгана. "
                         "Заагаагүй бол автоматаар: Raspberry Pi бол edge, "
                         "эс бөгөөс cloud"))
    p.add_argument("--label", default="run", help="CSV-д бичих шошго")
    p.add_argument("--seconds", type=float, default=180)
    p.add_argument("--interval", type=float, default=5)
    p.add_argument("--iface", default=None,
                   help="сүлжээний интерфейс (анхдагч: default route-ынх, ихэвчлэн eth0)")
    # ирмэгийн mosquitto ($SYS)
    p.add_argument("--mqtt-host", default="localhost",
                   help="edge: $SYS уншиж буй mosquitto-гийн хаяг")
    p.add_argument("--mqtt-port", type=int, default=1883)
    p.add_argument("--mqtt-user", default=os.environ.get("MQTT_USERNAME"))
    p.add_argument("--mqtt-password", default=os.environ.get("MQTT_PASSWORD"))
    # EMQX
    p.add_argument("--emqx", default=None,
                   help=("EMQX-ийн самбарын хаяг. cloud дээр анхдагч "
                         "http://localhost:18083; edge дээр өгөхгүй бол EMQX-ийг "
                         "асуухгүй (жишээ: http://192.168.1.100:18083)"))
    p.add_argument("--no-emqx", action="store_true",
                   help="EMQX-ийн REST API-г огт асуухгүй")
    p.add_argument("--emqx-key", default=os.environ.get("EMQX_API_KEY", ""),
                   help="EMQX API key (System → API Key); анхдагч $EMQX_API_KEY")
    p.add_argument("--emqx-secret", default=os.environ.get("EMQX_API_SECRET", ""))
    p.add_argument("--emqx-user", default="admin",
                   help="API key байхгүй үед /api/v5/login-д өгөх самбарын хэрэглэгч")
    p.add_argument("--emqx-password",
                   default=os.environ.get("EMQX_DASHBOARD_PASSWORD", "public"))
    p.add_argument("--outdir", default="measurements")
    a = p.parse_args()

    target = a.target or detect_target()
    emqx_url = a.emqx or ("http://localhost:18083" if target == "cloud" else None)
    emqx = None if (a.no_emqx or not emqx_url) else Emqx(
        emqx_url, a.emqx_key, a.emqx_secret, a.emqx_user, a.emqx_password)

    mosq = None
    if target == "edge":
        try:
            mosq = MosquittoSys(a.mqtt_host, a.mqtt_port, a.mqtt_user, a.mqtt_password)
        except Exception as exc:  # noqa: BLE001
            print(f"  mosquitto $SYS-д холбогдож чадсангүй: {exc}", file=sys.stderr)

    iface = a.iface or default_iface()
    counters = Counters(iface)
    counters.rates()                               # эхний утгыг тэмдэглэнэ

    os.makedirs(a.outdir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(a.outdir, f"loadtest-{target}-{a.label}-{stamp}.csv")

    print(f"→ Зорилт: {target}  ({'Raspberry Pi 3B — ирмэг' if target == 'edge' else 'зөөврийн компьютер — үүл'})")
    print(f"→ Брокерын үзүүлэлт: {'mosquitto $SYS @ ' + a.mqtt_host if target == 'edge' else 'EMQX REST @ ' + str(emqx_url)}")
    print(f"→ {a.seconds:.0f} сек, {a.interval:.0f} сек тутам, интерфейс {iface} → {path}")
    if target == "edge":
        print(f"→ Сул RAM {EDGE_RAM_WARN_MIB} MiB-ээс доош орвол, swap идэвхжвэл эсвэл "
              f"throttle илэрвэл анхааруулна.")
    print(f"{'үлдсэн':>8} {'холболт':>9} {'мсж/с':>9} {'CPU%':>7} "
          f"{'сул MiB':>9} {'tx Mbit':>8} {'swap o/s':>8} {'°C':>6}")

    t0 = time.time()
    prev_rx, prev_t = None, None
    warned = {"ram": False, "thr": False, "swap": False}
    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            while (elapsed := time.time() - t0) < a.seconds:
                row: dict[str, object] = {k: "" for k in FIELDS}
                row["ts"] = datetime.now(timezone.utc).isoformat()
                row["elapsed_s"] = round(elapsed, 1)
                row["target"] = target
                row["label"] = a.label
                if emqx:
                    row.update(emqx.metrics())
                row.update(docker_stats())
                row.update(system_stats())
                row.update(counters.rates())

                if mosq:
                    row.update(mosq.snapshot())
                elif target == "cloud":
                    # EMQX-ийн хуримтлагдсан messages.received-ээс хурд гаргана
                    now, cur = time.time(), row.get("emqx_msg_received")
                    if prev_rx not in (None, "") and cur not in (None, ""):
                        try:
                            row["broker_msg_in_rate"] = round(
                                (int(cur) - int(prev_rx)) / (now - prev_t), 1)
                        except (TypeError, ValueError, ZeroDivisionError):
                            pass
                    prev_rx, prev_t = cur, now
                    row["broker_connections"] = row.get("emqx_connections", "")
                    row["broker_dropped_total"] = row.get("emqx_msg_dropped", "")

                if target == "edge":
                    avail = row.get("mem_available_mib")
                    if isinstance(avail, (int, float)) and avail < EDGE_RAM_WARN_MIB \
                            and not warned["ram"]:
                        warned["ram"] = True
                        print(f"\n  ⚠⚠ САНАХ ОЙ БАГАСЛАА: {avail} MiB сул "
                              f"(хязгаар {EDGE_RAM_WARN_MIB} MiB).\n", file=sys.stderr)
                    so = row.get("swap_out_pages_s")
                    if isinstance(so, (int, float)) and so > 0 and not warned["swap"]:
                        warned["swap"] = True
                        print("\n  ⚠⚠ SWAP ИДЭВХЖЛЭЭ (swap out > 0). Энэ шатнаас "
                              "хойшхи саатлын тоо ХҮЧИНГҮЙ — зогсоо.\n", file=sys.stderr)
                    thr = str(row.get("throttled", ""))
                    if thr and thr != "0x0" and not warned["thr"]:
                        warned["thr"] = True
                        print(f"\n  ⚠⚠ THROTTLE ИЛЭРЛЭЭ: {thr}. Тэжээл сул эсвэл халуун "
                              f"байна. Энэ ажиллалтын БҮХ ТОО ХҮЧИНГҮЙ — засаад "
                              f"дахин хэмжинэ үү.\n", file=sys.stderr)

                w.writerow(row)
                f.flush()
                print(f"{a.seconds-elapsed:8.0f} {str(row['broker_connections']):>9} "
                      f"{str(row['broker_msg_in_rate']):>9} "
                      f"{str(row.get('cpu_total_pct','')):>7} "
                      f"{str(row.get('mem_available_mib','')):>9} "
                      f"{str(row.get('net_tx_mbit','')):>8} "
                      f"{str(row.get('swap_out_pages_s','')):>8} "
                      f"{str(row.get('temp_c','')):>6}")
                time.sleep(a.interval)
    except KeyboardInterrupt:
        print("\n→ Тасаллаа (Ctrl+C).")
    finally:
        if mosq:
            mosq.close()

    print(f"\n→ Бичигдлээ: {path}")
    print("  Дараа нь (нэг муруй):")
    print(f"    python3 lab04/plot_scaling.py {path}")
    print("  Хоёр хостыг НЭГ ТЭНХЛЭГ дээр харьцуулах:")
    print("    python3 lab04/plot_scaling.py measurements/loadtest-edge-*.csv "
          "measurements/loadtest-cloud-*.csv --out lab04/scaling.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
