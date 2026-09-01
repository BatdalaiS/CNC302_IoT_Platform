#!/usr/bin/env python3
"""
CNC302 Лаб 3 — Unified Namespace-ийг судлах ба ШАЛГАХ

Хоёр үүрэгтэй:
  1. Брокер дээр яг одоо ямар сэдвүүд амьд байгааг МОД хэлбэрээр харуулна
  2. Сэдвийн нэршил ISA-95 схемд нийцэж байгааг ШАЛГАНА

ISA-95-д тулгуурласан бидний схем:

    <prefix>/<site>/<area>/<line>/<device>/<channel>
       │        │      │      │       │        └─ telemetry | status | cmd | event
       │        │      │      │       └────────── төхөөрөмжийн ID
       │        │      │      └────────────────── үйлдвэрлэлийн шугам / бүлэг
       │        │      └───────────────────────── талбай / барилга
       │        └──────────────────────────────── байршил / үйлдвэр
       └───────────────────────────────────────── байгууллагын угтвар

Жишээ:
  python uns_tree.py --host pi-team03.local --seconds 30
  python uns_tree.py --host pi-team03.local --seconds 30 --json uns.json
  python uns_tree.py --host pi-team03.local --filter 'cnc302/#' --strict
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import defaultdict

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

CHANNELS = {"telemetry", "status", "cmd", "event", "attributes"}
SEG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")


class TopicStat:
    __slots__ = ("count", "bytes", "first", "last", "retained", "qos")

    def __init__(self) -> None:
        self.count = 0
        self.bytes = 0
        self.first = 0.0
        self.last = 0.0
        self.retained = False
        self.qos = 0

    def add(self, n: int, retained: bool, qos: int) -> None:
        now = time.time()
        if not self.count:
            self.first = now
        self.last = now
        self.count += 1
        self.bytes += n
        self.retained = self.retained or retained
        self.qos = max(self.qos, qos)

    @property
    def rate(self) -> float:
        span = self.last - self.first
        return self.count / span if span > 0.5 else 0.0


def validate(topic: str, prefix: str) -> list[str]:
    """Сэдвийн нэршлийн зөрчлүүдийг буцаана."""
    problems = []
    parts = topic.split("/")

    if parts[0] != prefix:
        problems.append(f"угтвар '{parts[0]}' ≠ '{prefix}'")
    if len(parts) != 6:
        problems.append(f"{len(parts)} хэсэгтэй, 6 байх ёстой "
                        "(prefix/site/area/line/device/channel)")
    if len(parts) >= 6 and parts[5] not in CHANNELS:
        problems.append(f"суваг '{parts[5]}' зөвшөөрөгдөөгүй "
                        f"({'|'.join(sorted(CHANNELS))})")
    for i, seg in enumerate(parts):
        if not SEG_RE.match(seg):
            problems.append(f"{i}-р хэсэг '{seg}': зөвхөн жижиг үсэг, тоо, "
                            ". _ - зөвшөөрнө, 32 тэмдэгтээс богино")
    if "+" in topic or "#" in topic:
        problems.append("хэвлэсэн сэдэвт орлуулагч тэмдэг байж болохгүй")
    return problems


def render_tree(stats: dict[str, TopicStat]) -> None:
    tree: dict = {}
    for topic in sorted(stats):
        node = tree
        for seg in topic.split("/"):
            node = node.setdefault(seg, {})
        node["__leaf__"] = stats[topic]

    def walk(node: dict, path: list[str], depth: int) -> None:
        keys = [k for k in node if k != "__leaf__"]
        for i, k in enumerate(sorted(keys)):
            last = i == len(keys) - 1
            branch = "└─ " if last else "├─ "
            indent = "".join("   " if p else "│  " for p in path)
            child = node[k]
            leaf: TopicStat | None = child.get("__leaf__")
            label = f"{indent}{branch}{k}"
            if leaf:
                label += (f"   [{leaf.count} мсж, {leaf.rate:5.2f}/с, "
                          f"{leaf.bytes/max(leaf.count,1):.0f}Б дундаж"
                          f"{', retained' if leaf.retained else ''}"
                          f", QoS{leaf.qos}]")
            print(label)
            walk(child, path + [last], depth + 1)

    walk(tree, [], 0)


def main() -> int:
    p = argparse.ArgumentParser(description="Unified Namespace explorer/validator")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--username")
    p.add_argument("--password")
    p.add_argument("--filter", default="#", help="захиалах хэв (default: бүгд)")
    p.add_argument("--prefix", default="cnc302", help="хүлээгдэж буй угтвар")
    p.add_argument("--seconds", type=float, default=30.0)
    p.add_argument("--strict", action="store_true",
                   help="зөрчил илэрвэл 1 кодоор гарах (CI-д ашиглана)")
    p.add_argument("--json", help="үр дүнг JSON болгон бичих")
    a = p.parse_args()

    stats: dict[str, TopicStat] = defaultdict(TopicStat)

    def on_message(cl, u, m):
        stats[m.topic].add(len(m.payload), m.retain, m.qos)

    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="cnc302-uns-explorer",
                    protocol=mqtt.MQTTv5)
    if a.username:
        c.username_pw_set(a.username, a.password)
    c.on_message = on_message
    c.connect(a.host, a.port, keepalive=30)
    c.subscribe(a.filter, qos=0)
    c.loop_start()

    print(f"→ '{a.filter}' сэдвийг {a.seconds:.0f} секунд сонсож байна…",
          file=sys.stderr)
    time.sleep(a.seconds)
    c.loop_stop()
    c.disconnect()

    if not stats:
        print("\nМессеж ирсэнгүй. sim_device.py ажиллаж байна уу?", file=sys.stderr)
        return 1

    print(f"\n{'═'*72}\n  UNS МОД — {len(stats)} өвөрмөц сэдэв\n{'═'*72}")
    render_tree(stats)

    # ── нийлбэр ──
    total_msg = sum(s.count for s in stats.values())
    total_b = sum(s.bytes for s in stats.values())
    print(f"\nНийт: {total_msg} мессеж, {total_b/1024:.1f} KiB, "
          f"{total_msg/a.seconds:.1f} мсж/с")

    # ── шалгалт ──
    print(f"\n{'═'*72}\n  НЭРШЛИЙН ШАЛГАЛТ\n{'═'*72}")
    bad = 0
    for topic in sorted(stats):
        problems = validate(topic, a.prefix)
        if problems:
            bad += 1
            print(f"✗ {topic}")
            for pr in problems:
                print(f"    · {pr}")
    if bad == 0:
        print(f"✓ Бүх {len(stats)} сэдэв схемд нийцэж байна.")
    else:
        print(f"\n{bad}/{len(stats)} сэдэв схем зөрчсөн.")

    if a.json:
        out = {
            "captured_seconds": a.seconds,
            "topics": {
                t: {"count": s.count, "bytes": s.bytes,
                    "rate_msg_s": round(s.rate, 3),
                    "avg_payload_bytes": round(s.bytes / max(s.count, 1), 1),
                    "retained": s.retained, "max_qos": s.qos,
                    "violations": validate(t, a.prefix)}
                for t, s in sorted(stats.items())
            },
        }
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\nJSON: {a.json}", file=sys.stderr)

    return 1 if (a.strict and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
