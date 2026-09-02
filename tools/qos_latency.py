#!/usr/bin/env python3
"""
CNC302 — MQTT QoS-ийн саатал ба дамжуулах чадварын хэмжилт (Лаб 3)

Нэг процесс дотор нийтлэгч ба захиалагчийг зэрэг ажиллуулна. Тиймээс цагийн
зөрүү (clock skew) байхгүй — саатлыг шууд хэмжиж болно.

  илгээх агшин (ns)  ──MQTT──▶ брокер ──▶ хүлээн авах агшин (ns)
  саатал = хүлээн авсан − илгээсэн

── ГУРВАН ЗАМЫГ ХАРЬЦУУЛНА (--path) ────────────────────────────────────────
Стек хоёр хостод хуваагдсан тул нэг мессеж гурван өөр замаар явж болно.
`--path` нь ЗӨВХӨН ШОШГО: юу хэмжиж байгааг үр дүнд болон CSV-д тэмдэглэнэ.

  loopback  нийтлэгч ба брокер НЭГ машин дээр (localhost).
            Сүлжээ огт оролцохгүй → брокер өөрөө хэдэн мс иддэгийг харуулна.
  lan       зөөврийн компьютер → тэр компьютер дээрх EMQX рүү LAN-аар.
  bridge    Pi 3B → ирмэгийн mosquitto → ГҮҮР → зөөврийн EMQX.
            Хамгийн урт зам: хоёр брокер + 100 Mbit уплинк.

⚠ Pi 3B-гийн Ethernet нь USB 2.0 дээр сууж, USB-тэй зурвасаа хуваадаг. Тиймээс
  LAN болон bridge замын саатлын СҮҮЛ (tail) нь Pi 5-тай харьцуулахад хамаагүй
  өргөн байна. Дундаж (p50) сайхан харагдаж болох ч тэр нь ХУУРАМЧ тайтгарал:
  үйлдвэрийн систем дэх ХАРИУ ҮЙЛДЛИЙН БАТАЛГААГ p99 тодорхойлдог. Тайланд p50
  биш, **p99-ийг** гол тоо болгон бичнэ.

Жишээ:
  # Брокертойгоо нэг машин дээр — брокерын өөрийн саатал
  python qos_latency.py --path loopback --host localhost --qos 1 --count 500

  # Зөөврийн компьютер → EMQX, гурван QoS-ийг дараалан
  python qos_latency.py --path lan --host 192.168.1.100 --sweep --count 500

  # Pi дээрээс ажиллуулж, гүүрээр дамжих замыг хэмжих
  python qos_latency.py --path bridge --host localhost --qos 1 --count 500

  # Хуваалцсан захиалга (shared subscription) — 3 хэрэглэгч
  python qos_latency.py --path lan --host 192.168.1.100 --qos 1 --count 500 --shared 3

  # Үр дүнг CSV болгон хадгалах (тайланд оруулна)
  python qos_latency.py --path lan --host 192.168.1.100 --sweep --csv qos-lan.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
import threading
import time

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion


class Measurement:
    def __init__(self, expected: int) -> None:
        self.expected = expected
        self.latencies_ms: list[float] = []
        self.seen: set[int] = set()
        self.duplicates = 0
        self.done = threading.Event()
        self.first_rx: float | None = None
        self.last_rx: float | None = None
        self._lock = threading.Lock()

    def record(self, seq: int, sent_ns: int, rx_ns: int) -> None:
        with self._lock:
            if seq in self.seen:
                self.duplicates += 1
                return
            self.seen.add(seq)
            self.latencies_ms.append((rx_ns - sent_ns) / 1e6)
            if self.first_rx is None:
                self.first_rx = rx_ns
            self.last_rx = rx_ns
            if len(self.seen) >= self.expected:
                self.done.set()

    def summary(self, qos: int, payload_bytes: int, path: str = "loopback",
                host: str = "") -> dict:
        lat = sorted(self.latencies_ms)
        received = len(lat)
        lost = self.expected - received
        if received and self.first_rx and self.last_rx and self.last_rx > self.first_rx:
            span = (self.last_rx - self.first_rx) / 1e9
            throughput = received / span
        else:
            throughput = 0.0

        def pct(p: float) -> float:
            if not lat:
                return float("nan")
            k = min(int(round(p / 100.0 * (len(lat) - 1))), len(lat) - 1)
            return lat[k]

        return {
            "path": path,            # loopback | lan | bridge — аль замыг хэмжсэн
            "host": host,
            "qos": qos,
            "payload_bytes": payload_bytes,
            "sent": self.expected,
            "received": received,
            "lost": lost,
            "loss_pct": round(100.0 * lost / self.expected, 3) if self.expected else 0.0,
            "duplicates": self.duplicates,
            "p50_ms": round(pct(50), 3),
            "p95_ms": round(pct(95), 3),
            "p99_ms": round(pct(99), 3),
            "max_ms": round(lat[-1], 3) if lat else float("nan"),
            "mean_ms": round(statistics.fmean(lat), 3) if lat else float("nan"),
            "throughput_msg_s": round(throughput, 1),
        }


def make_client(name: str, host: str, port: int, username, password) -> mqtt.Client:
    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=name, protocol=mqtt.MQTTv5)
    if username:
        c.username_pw_set(username, password)
    c.connect(host, port, keepalive=30)
    return c


def run_once(args: argparse.Namespace, qos: int) -> dict:
    topic = f"{args.topic}/q{qos}"
    filler = "x" * max(0, args.payload - 120)   # ~120 байт нь толгойн талбарууд
    m = Measurement(args.count)

    # ── захиалагч(ид) ──
    sub_clients: list[mqtt.Client] = []
    n_subs = args.shared if args.shared else 1
    sub_topic = f"$share/cnc302grp/{topic}" if args.shared else topic

    def on_message(client, userdata, msg):
        rx = time.time_ns()
        try:
            d = json.loads(msg.payload)
            m.record(d["seq"], d["t"], rx)
        except Exception:  # noqa: BLE001
            pass

    for i in range(n_subs):
        c = make_client(f"cnc302-sub-{qos}-{i}", args.host, args.port,
                        args.username, args.password)
        c.on_message = on_message
        c.subscribe(sub_topic, qos=qos)
        c.loop_start()
        sub_clients.append(c)

    time.sleep(0.5)   # захиалга бүртгэгдэх хүртэл хүлээнэ

    # ── нийтлэгч ──
    pub = make_client(f"cnc302-pub-{qos}", args.host, args.port,
                      args.username, args.password)
    pub.loop_start()

    t0 = time.time()
    for seq in range(args.count):
        body = json.dumps({"seq": seq, "t": time.time_ns(), "pad": filler})
        pub.publish(topic, body, qos=qos)
        if args.interval > 0:
            time.sleep(args.interval)
    publish_span = time.time() - t0

    completed = m.done.wait(timeout=args.timeout)
    if not completed:
        print(f"  АНХААР: QoS {qos} — {args.timeout}s дотор бүх мессеж ирсэнгүй "
              f"({len(m.seen)}/{args.count})", file=sys.stderr)

    pub.loop_stop(); pub.disconnect()
    for c in sub_clients:
        c.loop_stop(); c.disconnect()

    res = m.summary(qos, args.payload, path=args.path, host=args.host)
    res["publish_span_s"] = round(publish_span, 3)
    res["publish_rate_msg_s"] = round(args.count / max(publish_span, 1e-6), 1)
    res["subscribers"] = n_subs
    return res


PATH_LABELS = {
    "loopback": "нийтлэгч ба брокер нэг машин дээр (сүлжээгүй)",
    "lan":      "зөөврийн компьютер → EMQX, LAN-аар",
    "bridge":   "Pi 3B → ирмэгийн mosquitto → гүүр → EMQX",
}


def print_table(rows: list[dict]) -> None:
    cols = ["path", "qos", "subscribers", "sent", "received", "lost", "loss_pct",
            "duplicates", "p50_ms", "p95_ms", "p99_ms", "max_ms",
            "publish_rate_msg_s", "throughput_msg_s"]
    head = ["Зам", "QoS", "Sub", "Илгээв", "Ирсэн", "Алдсан", "Алдалт%",
            "Давхар", "p50 мс", "p95 мс", "p99 мс", "max мс",
            "Илгээх/с", "Хүлээн/с"]
    widths = [max(len(h), 9) for h in head]
    print("  ".join(h.rjust(w) for h, w in zip(head, widths)))
    print("  ".join("-" * w for w in widths))
    for r in rows:
        print("  ".join(str(r[c]).rjust(w) for c, w in zip(cols, widths)))
    print("\n  ГОЛ ТОО нь p99 — дундаж биш. Pi 3B дээр 100 Mbit холбоос USB-тэй")
    print("  зурвасаа хуваадаг тул p50 сайн байхад p99 хэд дахин том гарч болно.")


def main() -> int:
    p = argparse.ArgumentParser(
        description="MQTT QoS саатал/чадварын хэмжилт",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--username")
    p.add_argument("--password")
    p.add_argument("--path", choices=["loopback", "lan", "bridge"],
                   default="loopback",
                   help=("хэмжиж буй ЗАМЫН шошго. Үр дүн болон CSV-д бичигдэнэ "
                         "тул гурван замыг хожим харьцуулж болно.  "
                         "loopback = " + PATH_LABELS["loopback"] + ";  "
                         "lan = " + PATH_LABELS["lan"] + ";  "
                         "bridge = " + PATH_LABELS["bridge"] + ".  "
                         "Анхдагч: loopback"))
    p.add_argument("--topic", default="cnc302/bench/latency")
    p.add_argument("--qos", type=int, default=1, choices=[0, 1, 2])
    p.add_argument("--count", type=int, default=500, help="мессежийн тоо")
    p.add_argument("--payload", type=int, default=200, help="ачааллын хэмжээ (байт)")
    p.add_argument("--interval", type=float, default=0.0,
                   help="илгээх завсар (сек). 0 = хамгийн хурдан")
    p.add_argument("--shared", type=int, default=0,
                   help="хуваалцсан захиалгын хэрэглэгчийн тоо (0 = энгийн захиалга)")
    p.add_argument("--timeout", type=float, default=30.0)
    p.add_argument("--sweep", action="store_true", help="QoS 0,1,2-ыг дараалан хэмжих")
    p.add_argument("--csv", help="үр дүнг CSV файлд бичих")
    args = p.parse_args()

    print(f"→ Зам: {args.path} — {PATH_LABELS[args.path]}", file=sys.stderr)
    print(f"→ Брокер: {args.host}:{args.port}", file=sys.stderr)
    if args.path in ("lan", "bridge"):
        print("→ Санамж: p99-ийг ажигла. Pi 3B-гийн 100 Mbit холбоос USB 2.0 дээр "
              "сууж байгаа тул саатлын сүүл өргөн байна.", file=sys.stderr)

    qos_list = [0, 1, 2] if args.sweep else [args.qos]
    rows = []
    for q in qos_list:
        print(f"→ QoS {q} хэмжиж байна ({args.count} мессеж, "
              f"{args.payload} байт, зам={args.path})…", file=sys.stderr)
        rows.append(run_once(args, q))
        time.sleep(1.0)

    print()
    print_table(rows)

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nCSV бичигдлээ: {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
