#!/usr/bin/env python3
"""
CNC302 — виртуал төхөөрөмжийн флот (MQTT 5.0)

Лаб 2-оос эхлэн бүх лабораторид хэрэглэгдэнэ.

── ХОЁР ХОСТЫН БҮТЭЦ, ХОЁР ЗОРИЛТ ──────────────────────────────────────────
Хичээлийн стек хоёр хостод хуваагдсан:

  · үүл  (cloud) — зөөврийн компьютер: EMQX, InfluxDB, Grafana, registry …
  · ирмэг (edge) — Raspberry Pi 3B: mosquitto + үүл рүү татсан гүүр (bridge)

Виртуал флотыг ХОЁУЛАНГИЙНХ НЬ аль руу ч чиглүүлж болно, гэхдээ утга нь өөр:

  --target cloud  → EMQX рүү шууд. Зөөврийн компьютер хүчирхэг тул энд
                    хязгаар нь ихэвчлэн олдохгүй. Энэ бол "жишиг шугам".
  --target edge   → Pi-гийн mosquitto руу. ЭНЭ НЬ СОНИРХОЛТОЙ ХЭМЖИЛТ:
                    бүх мессеж Pi-гаас гүүрээр дамжин 100 Mbit холбоосоор
                    гарна. Pi 3B дээр Ethernet нь USB 2.0 дээр сууж байгаа
                    тул бодит хурд ~90–95 Mbit бөгөөд USB-тэй өрсөлддөг.
                    Хязгаар нь CPU биш, ихэнхдээ RAM (1 GB) эсвэл уплинк.

`--target` нь зөвхөн АНХДАГЧ ЗӨВЛӨМЖИЙГ (хаяг/порт) л өөрчилнө; бодит хаягийг
`--host`/`--port` тодорхойлно — тэдгээр нь үргэлж давамгайлна.

Жишээ:
  # Брокергүйгээр ачааллыг шалгах (SETUP-ийн шалгалт)
  python sim_device.py --dry-run --devices 2 --count 3

  # 10 төхөөрөмж, 2 секунд тутам, зөөврийн компьютерийн EMQX рүү
  python sim_device.py --target cloud --host 192.168.1.100 --devices 10 --interval 2

  # Мөн 10 төхөөрөмж, харин Pi-гийн mosquitto руу (уплинкийг ачаална)
  python sim_device.py --target edge --host pi3b-01.local --devices 10 --interval 2

  # TLS + клиентийн сертификаттай (Лаб 2) — EMQX-ийн 8883
  python sim_device.py --target cloud --host 192.168.1.100 --port 8883 --tls \\
      --ca certs/ca.crt --cert certs/dev001.crt --key certs/dev001.key --devices 1

  # Гажил үүсгэх (Лаб 5, Лаб 6)
  python sim_device.py --target edge --host pi3b-01.local --devices 5 --anomaly-rate 0.05

Тэмдэглэл: 200-аас олон холболт шаардвал энэ скриптийн оронд `emqtt-bench`
ашиглана (Лаб 4-ийн зааврыг үзнэ үү). Pi-гийн mosquitto-д 200 холболт аль
хэдийн их ачаалал болохыг санаарай.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import signal
import ssl
import sys
import threading
import time
from dataclasses import dataclass, field

try:
    import paho.mqtt.client as mqtt
    from paho.mqtt.enums import CallbackAPIVersion
    from paho.mqtt.packettypes import PacketTypes
    from paho.mqtt.properties import Properties
except ImportError:  # pragma: no cover
    mqtt = None  # --dry-run горимд paho шаардлагагүй


# ──────────────────────────── тохиргоо ────────────────────────────

@dataclass
class Stats:
    published: int = 0
    errors: int = 0
    connects: int = 0
    disconnects: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def bump(self, field_name: str, n: int = 1) -> None:
        with self.lock:
            setattr(self, field_name, getattr(self, field_name) + n)


STOP = threading.Event()

# --target-ийн зөвлөмжүүд. Зөвхөн ТАЙЛБАР — холболтыг --host/--port шийднэ.
TARGET_HINTS = {
    "edge": {
        "host": "pi3b-01.local",
        "port": 1883,
        "what": "Raspberry Pi 3B дээрх mosquitto (ирмэгийн брокер)",
        "note": "мессеж Pi-гийн 100 Mbit уплинкээр гүүрдэнэ — энэ нь хэмжих гол зам",
    },
    "cloud": {
        "host": "192.168.1.100",
        "port": 1883,
        "what": "зөөврийн компьютер дээрх EMQX (үүлний брокер)",
        "note": "гүүрийг тойрч шууд холбогдоно — жишиг шугамын хэмжилт",
    },
}


def target_banner(args: argparse.Namespace) -> str:
    """Эхлэх үеийн товч мэдээлэл (--target-ийн дагуу)."""
    hint = TARGET_HINTS[args.target]
    used_default = args.host == "localhost"
    lines = [
        "─" * 72,
        f"  Зорилт (--target)  : {args.target} — {hint['what']}",
        f"  Анхдагч зөвлөмж    : {hint['host']}:{hint['port']}",
        f"  Бодит холболт      : {args.host}:{args.port}"
        + ("   ← --host заагаагүй тул localhost" if used_default else ""),
        f"  Тэмдэглэл          : {hint['note']}",
        f"  Флот               : {args.devices} төхөөрөмж, "
        f"{args.interval} сек тутам, QoS {args.qos}",
        f"  UNS угтвар         : {args.topic_prefix}/{args.site}/{args.area}/"
        f"<line>/<device>/telemetry",
        "─" * 72,
    ]
    if args.target == "edge" and used_default:
        lines.insert(
            -1,
            "  ⚠ --target edge боловч --host заагаагүй. Pi-гийн хаягийг өгнө үү, "
            "эс бөгөөс\n    уплинк огт ачаалагдахгүй.",
        )
    return "\n".join(lines)


# ──────────────────────── дохионы загварчлал ────────────────────────

def make_payload(device_id: str, seq: int, t: float, anomaly: bool) -> dict:
    """
    Бодит мэдрэгчид ойролцоо дохио үүсгэнэ:
      - температур: 24 хэмийн эргэн тойронд удаан хэлбэлзэл + шуугиан
      - чийг: температуртай сөрөг хамааралтай
      - чичиргээ: RMS утга; гажлын үед 4-8 дахин өснө
    """
    slow = math.sin(t / 300.0)          # ~5 минутын мөчлөг
    fast = math.sin(t / 7.0)            # хурдан хэлбэлзэл

    temperature = 24.0 + 3.0 * slow + random.gauss(0, 0.15)
    humidity = 45.0 - 8.0 * slow + random.gauss(0, 0.4)
    vibration = 0.35 + 0.05 * fast + abs(random.gauss(0, 0.02))

    status = "ok"
    if anomaly:
        vibration *= random.uniform(4.0, 8.0)
        temperature += random.uniform(6.0, 12.0)
        status = "anomaly"

    return {
        "ts": int(t * 1000),
        "device_id": device_id,
        "seq": seq,
        "temperature": round(temperature, 3),
        "humidity": round(humidity, 2),
        "vibration_rms": round(vibration, 4),
        "status": status,
    }


def uns_topic(prefix: str, site: str, area: str, line: str, device_id: str) -> str:
    """
    ISA-95 шатлалд тулгуурласан Unified Namespace сэдэв (Лаб 3).
      <prefix>/<site>/<area>/<line>/<device>/telemetry
    """
    return f"{prefix}/{site}/{area}/{line}/{device_id}/telemetry"


# ──────────────────────── нэг төхөөрөмжийн ажил ────────────────────────

def device_worker(idx: int, args: argparse.Namespace, stats: Stats) -> None:
    device_id = f"{args.prefix_id}{idx:04d}"
    line = f"line{(idx % max(1, args.lines)) + 1:02d}"
    topic = uns_topic(args.topic_prefix, args.site, args.area, line, device_id)

    client = mqtt.Client(
        CallbackAPIVersion.VERSION2,
        client_id=device_id,
        protocol=mqtt.MQTTv5,
        clean_session=None,
    )

    if args.username:
        client.username_pw_set(args.username, args.password)

    if args.tls:
        client.tls_set(
            ca_certs=args.ca,
            certfile=args.cert,
            keyfile=args.key,
            cert_reqs=ssl.CERT_REQUIRED if args.ca else ssl.CERT_NONE,
            tls_version=ssl.PROTOCOL_TLS_CLIENT,
        )
        if args.insecure:
            client.tls_insecure_set(True)

    # Last Will — төхөөрөмж гэнэт унтарвал брокер энэ мессежийг нийтэлнэ (Лаб 3)
    will_topic = f"{args.topic_prefix}/{args.site}/{args.area}/{line}/{device_id}/status"
    client.will_set(will_topic, json.dumps({"online": False}), qos=1, retain=True)

    def on_connect(cl, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            stats.bump("connects")
            cl.publish(will_topic, json.dumps({"online": True}), qos=1, retain=True)
        else:
            stats.bump("errors")
            print(f"[{device_id}] холбогдож чадсангүй: {reason_code}", file=sys.stderr)

    def on_disconnect(cl, userdata, disconnect_flags, reason_code, properties=None):
        stats.bump("disconnects")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        client.connect(args.host, args.port, keepalive=args.keepalive)
    except Exception as exc:  # noqa: BLE001
        stats.bump("errors")
        print(f"[{device_id}] холболтын алдаа: {exc}", file=sys.stderr)
        return

    client.loop_start()

    # MQTT 5.0 — мессежийн хүчинтэй хугацаа (Лаб 3-т үүнийг туршина)
    props = Properties(PacketTypes.PUBLISH)
    if args.message_expiry:
        props.MessageExpiryInterval = args.message_expiry

    seq = 0
    # төхөөрөмжүүд яг нэг агшинд бөөнөөрөө илгээхгүйн тулд эхлэлийг тараана
    time.sleep(random.uniform(0, min(args.interval, 1.0)))

    while not STOP.is_set():
        seq += 1
        anomaly = random.random() < args.anomaly_rate
        payload = make_payload(device_id, seq, time.time(), anomaly)
        info = client.publish(
            topic, json.dumps(payload), qos=args.qos, retain=False, properties=props
        )
        if info.rc == mqtt.MQTT_ERR_SUCCESS:
            stats.bump("published")
        else:
            stats.bump("errors")

        if args.count and seq >= args.count:
            break
        STOP.wait(args.interval)

    client.publish(will_topic, json.dumps({"online": False}), qos=1, retain=True)
    time.sleep(0.2)
    client.loop_stop()
    client.disconnect()


# ──────────────────────────── dry-run горим ────────────────────────────

def dry_run(args: argparse.Namespace) -> None:
    print("# --dry-run: брокерт холбогдохгүй, зөвхөн ачааллыг хэвлэнэ\n")
    for idx in range(args.devices):
        device_id = f"{args.prefix_id}{idx:04d}"
        line = f"line{(idx % max(1, args.lines)) + 1:02d}"
        topic = uns_topic(args.topic_prefix, args.site, args.area, line, device_id)
        for seq in range(1, (args.count or 1) + 1):
            payload = make_payload(
                device_id, seq, time.time() + seq * args.interval,
                random.random() < args.anomaly_rate,
            )
            print(f"{topic}  {json.dumps(payload, ensure_ascii=False)}")


# ──────────────────────────── үндсэн хэсэг ────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="CNC302 виртуал төхөөрөмжийн флот",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    conn = p.add_argument_group("холболт")
    conn.add_argument(
        "--target", choices=["edge", "cloud"], default="cloud",
        help=("аль брокер рүү чиглэж байгааг заана. Зөвхөн анхдагч ЗӨВЛӨМЖ ба "
              "эхлэх мэдээллийг өөрчилнө — бодит хаягийг --host шийднэ.  "
              f"edge = {TARGET_HINTS['edge']['host']}:{TARGET_HINTS['edge']['port']} "
              "(Pi 3B mosquitto, 100 Mbit уплинкийг ачаална);  "
              f"cloud = {TARGET_HINTS['cloud']['host']}:{TARGET_HINTS['cloud']['port']} "
              "(зөөврийн компьютерийн EMQX). Анхдагч: cloud"))
    conn.add_argument("--host", default="localhost",
                      help="брокерийн хаяг (--target-ийн зөвлөмжөөс давамгайлна)")
    conn.add_argument("--port", type=int, default=1883)
    conn.add_argument("--keepalive", type=int, default=60)
    conn.add_argument("--username")
    conn.add_argument("--password")
    conn.add_argument("--tls", action="store_true", help="TLS ашиглах")
    conn.add_argument("--ca", help="CA сертификат")
    conn.add_argument("--cert", help="клиентийн сертификат")
    conn.add_argument("--key", help="клиентийн хувийн түлхүүр")
    conn.add_argument("--insecure", action="store_true",
                      help="серверийн нэрийг шалгахгүй (зөвхөн лабораторид)")

    fleet = p.add_argument_group("флот")
    fleet.add_argument("--devices", type=int, default=1, help="төхөөрөмжийн тоо")
    fleet.add_argument("--prefix-id", default="dev", help="төхөөрөмжийн ID-ийн угтвар")
    fleet.add_argument("--interval", type=float, default=2.0, help="илгээх завсар (сек)")
    fleet.add_argument("--count", type=int, default=0,
                       help="төхөөрөмж тус бүрийн мессежийн тоо (0 = хязгааргүй)")
    fleet.add_argument("--qos", type=int, default=1, choices=[0, 1, 2])
    fleet.add_argument("--message-expiry", type=int, default=0,
                       help="MQTT 5.0 Message Expiry Interval (сек, 0 = хэрэглэхгүй)")
    fleet.add_argument("--anomaly-rate", type=float, default=0.0,
                       help="гажлын магадлал 0..1")

    uns = p.add_argument_group("Unified Namespace")
    uns.add_argument("--topic-prefix", default="cnc302")
    # Анхдагчууд нь edge/.env.example болон гүүрний bridge.conf-той тааруулсан:
    # гүүр нь cnc302/<site>/# сэдвийг л үүл рүү дамжуулдаг тул site таарах ёстой.
    uns.add_argument("--site", default="shutis")
    uns.add_argument("--area", default="mhts")
    uns.add_argument("--lines", type=int, default=2, help="үйлдвэрлэлийн шугамын тоо")

    p.add_argument("--dry-run", action="store_true",
                   help="брокергүйгээр ачааллыг хэвлэх")
    p.add_argument("--stats-interval", type=float, default=10.0,
                   help="статистик хэвлэх завсар (сек)")
    return p


def main() -> int:
    args = build_parser().parse_args()

    print(target_banner(args), file=sys.stderr)

    if args.dry_run:
        if not args.count:
            args.count = 1
        dry_run(args)
        return 0

    if mqtt is None:
        print("paho-mqtt суулгаагүй байна:  pip install -r tools/requirements.txt",
              file=sys.stderr)
        return 2

    if args.devices > 200:
        print("АНХААР: 200-аас олон холболтод emqtt-bench ашиглана уу "
              "(Лаб 4-ийн заавар).", file=sys.stderr)
    if args.target == "edge" and args.devices > 100:
        print("АНХААР: Pi 3B-гийн mosquitto руу 100-аас олон холболт өгч байна. "
              "Хэмжилтийн зэрэгцээ `tools/measure_stack.sh --role edge --watch` "
              "ажиллуулж, сул RAM болон throttle-ыг заавал бүртгэ.",
              file=sys.stderr)

    stats = Stats()

    def handle_sigint(signum, frame):  # noqa: ARG001
        print("\nЗогсоож байна…", file=sys.stderr)
        STOP.set()

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    threads = [
        threading.Thread(target=device_worker, args=(i, args, stats), daemon=True)
        for i in range(args.devices)
    ]
    started = time.time()
    for t in threads:
        t.start()

    last = 0
    while any(t.is_alive() for t in threads):
        STOP.wait(args.stats_interval)
        elapsed = time.time() - started
        rate = (stats.published - last) / max(args.stats_interval, 0.001)
        last = stats.published
        print(
            f"[{elapsed:7.1f}s] илгээсэн={stats.published:<8d} "
            f"хурд={rate:7.1f} мсж/с  холболт={stats.connects:<5d} "
            f"тасалдал={stats.disconnects:<5d} алдаа={stats.errors}",
            file=sys.stderr,
        )
        if STOP.is_set():
            break

    for t in threads:
        t.join(timeout=5)

    elapsed = time.time() - started
    print(
        f"\nДүн: {stats.published} мессеж / {elapsed:.1f} сек = "
        f"{stats.published / max(elapsed, 0.001):.1f} мсж/с, алдаа {stats.errors}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
