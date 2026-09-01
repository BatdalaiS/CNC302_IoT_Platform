#!/usr/bin/env python3
"""
CNC302 Лаб 3 — Sparkplug B-ийн ҮЗЭЛ БАРИМТЛАЛЫН хялбаршуулсан хувилбар

⚠ ЭНЭ БОЛ ЖИНХЭНЭ SPARKPLUG B БИШ.
Жинхэнэ Sparkplug B нь Google Protocol Buffers ашигладаг. Энд бид уншихад
хялбар байлгах үүднээс JSON ашиглав. Сэдвийн бүтэц, төлөвийн машин,
дарааллын дугаар (seq), метрикийн alias — эдгээр нь стандартын дагуу.

Sparkplug B яагаад хэрэгтэй вэ? Энгийн MQTT нь "хэн ямар өгөгдөл нийтэлж
байгааг" тодорхойлдоггүй. Sparkplug B гурван зүйлийг нэмнэ:

  1. ТӨРӨЛХ СЭДВИЙН БҮТЭЦ
     spBv1.0/<group_id>/<message_type>/<edge_node_id>[/<device_id>]

  2. ТӨРӨЛХ ЦЭГ (birth/death certificate)
     NBIRTH — зангилаа сүлжээнд орлоо, БҮХ метрикээ зарлана
     DBIRTH — түүний доорх төхөөрөмж орлоо
     NDATA/DDATA — өөрчлөгдсөн метрик (зөвхөн өөрчлөгдсөнийг!)
     NDEATH — зангилаа салав (MQTT-ийн Last Will-ээр АВТОМАТААР)
     STATE  — платформын (primary application) төлөв

  3. ДАРААЛЛЫН ДУГААР (seq 0..255)
     Хэрэглэгч мессеж алдсан эсэхээ шууд мэдэж, шаардвал дахин BIRTH
     хүсэх боломжтой. Энгийн MQTT-д үүнийг мэдэх арга байхгүй.

Жишээ:
  # Зангилаа (edge node) ажиллуулах
  python sparkplug_lite.py node --host pi-team03.local --devices 2 --seconds 60

  # Ажиглагч (платформ талын хэрэглэгч)
  python sparkplug_lite.py monitor --host pi-team03.local --seconds 60

  # Дарааллын тасалдлыг зориудаар үүсгэх
  python sparkplug_lite.py node --host pi-team03.local --drop-seq 5
"""
from __future__ import annotations

import argparse
import json
import random
import signal
import sys
import time

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

NS = "spBv1.0"
STOP = False


def topic(group: str, mtype: str, node: str, device: str | None = None) -> str:
    t = f"{NS}/{group}/{mtype}/{node}"
    return f"{t}/{device}" if device else t


def metric(name: str, alias: int, value, dtype: str = "Double") -> dict:
    return {"name": name, "alias": alias, "timestamp": int(time.time() * 1000),
            "dataType": dtype, "value": value}


# ─────────────────────────── EDGE NODE ───────────────────────────

def run_node(a) -> None:
    global STOP
    group, node = a.group, a.node
    seq = 0
    bd_seq = 0

    def next_seq() -> int:
        nonlocal seq
        s = seq
        seq = (seq + 1) % 256
        return s

    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id=f"spb-{node}",
                    protocol=mqtt.MQTTv5)
    if a.username:
        c.username_pw_set(a.username, a.password)

    # NDEATH нь Last Will — зангилаа гэнэт унтарвал брокер өөрөө нийтэлнэ.
    # Энэ бол Sparkplug-ийн гол санаа: "үхлийн гэрчилгээ" урьдчилан бүртгэгддэг.
    ndeath = {"timestamp": int(time.time() * 1000),
              "metrics": [metric("bdSeq", 0, bd_seq, "Int64")], "seq": None}
    c.will_set(topic(group, "NDEATH", node), json.dumps(ndeath), qos=1, retain=False)

    c.connect(a.host, a.port, keepalive=30)
    c.loop_start()

    # ── NBIRTH: бүх метрикийг alias-тай нь зарлана ──
    node_metrics = [
        metric("bdSeq", 0, bd_seq, "Int64"),
        metric("Node Control/Rebirth", 1, False, "Boolean"),
        metric("Properties/Hardware", 2, "Raspberry Pi 5", "String"),
        metric("Properties/OS", 3, "Raspberry Pi OS 64-bit", "String"),
    ]
    c.publish(topic(group, "NBIRTH", node),
              json.dumps({"timestamp": int(time.time() * 1000),
                          "metrics": node_metrics, "seq": next_seq()}),
              qos=1)
    print(f"→ NBIRTH  {topic(group,'NBIRTH',node)}  seq=0")

    # ── DBIRTH: доорх төхөөрөмж бүр ──
    devices = [f"dev{i:02d}" for i in range(a.devices)]
    aliases = {"temperature": 10, "humidity": 11, "vibration": 12}
    for d in devices:
        dm = [metric("temperature", aliases["temperature"], 24.0),
              metric("humidity", aliases["humidity"], 45.0),
              metric("vibration", aliases["vibration"], 0.35)]
        c.publish(topic(group, "DBIRTH", node, d),
                  json.dumps({"timestamp": int(time.time() * 1000),
                              "metrics": dm, "seq": next_seq()}), qos=1)
        print(f"→ DBIRTH  {d}  seq={seq-1}  ({len(dm)} метрик зарлав)")

    # ── DDATA: зөвхөн ӨӨРЧЛӨГДСӨН метрик, alias-аар ──
    print(f"\n→ DDATA илгээж эхэллээ ({a.seconds}s). "
          f"Анхаар: нэр биш ALIAS дамжина.\n")
    last: dict[str, dict[str, float]] = {d: {} for d in devices}
    t_end = time.time() + a.seconds
    sent = 0
    while time.time() < t_end and not STOP:
        for d in devices:
            vals = {"temperature": round(24 + random.gauss(0, 1.2), 2),
                    "humidity": round(45 + random.gauss(0, 2.0), 1),
                    "vibration": round(0.35 + abs(random.gauss(0, 0.05)), 3)}
            changed = [metric("", aliases[k], v)
                       for k, v in vals.items()
                       if abs(v - last[d].get(k, -999)) > a.deadband]
            last[d] = vals
            if not changed:
                continue
            s = next_seq()
            if a.drop_seq and sent == a.drop_seq:
                print(f"  ⚠ seq={s} ЗОРИУДААР АЛГАСАВ (тасалдал үүсгэв)")
                sent += 1
                continue
            c.publish(topic(group, "DDATA", node, d),
                      json.dumps({"timestamp": int(time.time() * 1000),
                                  "metrics": changed, "seq": s}), qos=1)
            sent += 1
        time.sleep(a.interval)

    # ── Зөв салалт: NDEATH-ийг өөрөө нийтэлнэ ──
    bd_seq += 1
    c.publish(topic(group, "NDEATH", node),
              json.dumps({"timestamp": int(time.time() * 1000),
                          "metrics": [metric("bdSeq", 0, bd_seq, "Int64")]}), qos=1)
    print(f"\n→ NDEATH  (зөв салалт).  Нийт {sent} DDATA илгээв.")
    time.sleep(0.5)
    c.loop_stop()
    c.disconnect()


# ─────────────────────────── MONITOR ───────────────────────────

def run_monitor(a) -> None:
    seen_seq: dict[str, int] = {}
    gaps: list[str] = []
    counts = {"NBIRTH": 0, "DBIRTH": 0, "DDATA": 0, "NDATA": 0, "NDEATH": 0}
    known_aliases: dict[int, str] = {}

    def on_message(cl, u, m):
        parts = m.topic.split("/")
        if len(parts) < 4:
            return
        mtype, node = parts[2], parts[3]
        counts[mtype] = counts.get(mtype, 0) + 1
        try:
            body = json.loads(m.payload)
        except Exception:  # noqa: BLE001
            return
        seq = body.get("seq")

        if mtype in ("NBIRTH", "DBIRTH"):
            for met in body.get("metrics", []):
                if met.get("name"):
                    known_aliases[met["alias"]] = met["name"]
            print(f"◆ {mtype:<7} {m.topic}  seq={seq}  "
                  f"метрик={len(body.get('metrics', []))}")
            seen_seq[node] = seq if seq is not None else -1
            return

        if mtype == "NDEATH":
            print(f"✖ NDEATH  {node} салав "
                  f"(bdSeq={body.get('metrics',[{}])[0].get('value')})")
            return

        # DDATA — дарааллыг шалгана
        prev = seen_seq.get(node)
        if prev is not None and seq is not None:
            expect = (prev + 1) % 256
            if seq != expect:
                msg = (f"⚠ ДАРААЛЛЫН ТАСАЛДАЛ {node}: "
                       f"хүлээсэн seq={expect}, ирсэн seq={seq}")
                print(msg)
                gaps.append(msg)
            seen_seq[node] = seq

        names = [known_aliases.get(met["alias"], f"alias:{met['alias']}")
                 for met in body.get("metrics", [])]
        vals = [met["value"] for met in body.get("metrics", [])]
        pairs = ", ".join(f"{n}={v}" for n, v in zip(names, vals))
        print(f"  {mtype:<7} {parts[-1]:<8} seq={seq:<4} {pairs}")

    c = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="spb-monitor",
                    protocol=mqtt.MQTTv5)
    if a.username:
        c.username_pw_set(a.username, a.password)
    c.on_message = on_message
    c.connect(a.host, a.port, keepalive=30)
    c.subscribe(f"{NS}/{a.group}/#", qos=1)
    c.loop_start()
    print(f"→ {NS}/{a.group}/# сонсож байна ({a.seconds}s)…\n")
    t_end = time.time() + a.seconds
    while time.time() < t_end and not STOP:
        time.sleep(0.2)
    c.loop_stop(); c.disconnect()

    print(f"\n{'═'*60}\n  ДҮН\n{'═'*60}")
    for k, v in counts.items():
        print(f"  {k:<8} {v}")
    print(f"  Танигдсан alias: {len(known_aliases)} "
          f"({', '.join(f'{k}={v}' for k, v in sorted(known_aliases.items())[:5])}…)")
    if gaps:
        print(f"\n  ⚠ {len(gaps)} дарааллын тасалдал илэрлээ:")
        for g in gaps:
            print(f"    {g}")
        print("\n  Жинхэнэ системд платформ энэ үед 'Node Control/Rebirth' "
              "метрикийг True болгож зангилаанаас NBIRTH-ийг дахин хүснэ.")
    else:
        print("\n  ✓ Дарааллын тасалдал илрээгүй.")


def main() -> int:
    global STOP
    p = argparse.ArgumentParser(
        description="Sparkplug B (хялбаршуулсан) — үзэл баримтлалын лаборатори",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("cmd", choices=["node", "monitor"])
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--username")
    p.add_argument("--password")
    p.add_argument("--group", default="cnc302")
    p.add_argument("--node", default="edge01")
    p.add_argument("--devices", type=int, default=2)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--seconds", type=float, default=30.0)
    p.add_argument("--deadband", type=float, default=0.0,
                   help="энэ хэмжээнээс бага өөрчлөлтийг илгээхгүй (report-by-exception)")
    p.add_argument("--drop-seq", type=int, default=0,
                   help="N дэх мессежийг зориудаар алгасаж тасалдал үүсгэх")
    a = p.parse_args()

    def stop(*_):
        global STOP
        STOP = True
    signal.signal(signal.SIGINT, stop)

    (run_node if a.cmd == "node" else run_monitor)(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
