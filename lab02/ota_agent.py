#!/usr/bin/env python3
"""
CNC302 Лаб 2 — OTA шинэчлэлийн агент (ThingsBoard MQTT протокол)

Энэ бол *төхөөрөмж талын* агент. ThingsBoard дээр firmware байршуулаад
төхөөрөмжид оноох үед энэ агент түүнийг татаж, шалгаж, "суулгаж", төлөвөө
буцаан мэдээлнэ. Амжилтгүй болвол өмнөх хувилбар руу буцна (rollback).

ThingsBoard-ын OTA протоколын урсгал:

  1. Агент → v1/devices/me/attributes/request/1
        {"sharedKeys":"fw_title,fw_version,fw_size,fw_checksum,fw_checksum_algorithm"}
  2. Платформ → v1/devices/me/attributes/response/1        (одоогийн firmware)
     Платформ → v1/devices/me/attributes                    (шинэ firmware оноогдоход)
  3. Агент → v2/fw/request/{rid}/chunk/{cid}   ачаалал = хэсгийн хэмжээ (байт)
     Платформ → v2/fw/response/{rid}/chunk/{cid}  ачаалал = хоёртын өгөгдөл
  4. Агент → v1/devices/me/telemetry
        {"fw_state":"DOWNLOADING"|"DOWNLOADED"|"VERIFIED"|"UPDATING"|"UPDATED"|"FAILED"}

Жишээ:
  # Нэг төхөөрөмж, амжилттай шинэчлэл
  python ota_agent.py --host pi-team03.local --token <ACCESS_TOKEN>

  # Canary тараалт: 10 төхөөрөмжийн 30% нь амжилтгүй болно
  python ota_agent.py --host pi-team03.local --tokens-csv bulk.csv \\
      --devices 10 --fail-rate 0.3

  # Буцаалтыг ажиглах
  python ota_agent.py --host pi-team03.local --token <T> --fail-rate 1.0 --verbose
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import threading
import time

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

CHUNK_SIZE = 8192
SHARED_KEYS = "fw_title,fw_version,fw_size,fw_checksum,fw_checksum_algorithm"

TOPIC_ATTR_REQ = "v1/devices/me/attributes/request/{rid}"
TOPIC_ATTR_RESP = "v1/devices/me/attributes/response/+"
TOPIC_ATTR_PUSH = "v1/devices/me/attributes"
TOPIC_FW_REQ = "v2/fw/request/{rid}/chunk/{cid}"
TOPIC_FW_RESP = "v2/fw/response/+/chunk/+"
TOPIC_TELEMETRY = "v1/devices/me/telemetry"


class OtaDevice:
    """Нэг төхөөрөмжийн OTA агент."""

    def __init__(self, token: str, args: argparse.Namespace, name: str = "") -> None:
        self.token = token
        self.name = name or token[:8]
        self.args = args
        self.rid = random.randint(1000, 9999)
        self.buf = bytearray()
        self.expect_size = 0
        self.checksum = ""
        self.algo = "SHA256"
        self.title = ""
        self.version = ""
        self.current_version = "1.0.0"      # "суулгаастай" хувилбар
        self.finished = threading.Event()
        self.outcome = "NO_UPDATE"
        self.t_start = 0.0
        self.t_end = 0.0

        self.c = mqtt.Client(CallbackAPIVersion.VERSION2,
                             client_id=f"ota-{self.name}", protocol=mqtt.MQTTv5)
        self.c.username_pw_set(token)
        self.c.on_connect = self._on_connect
        self.c.on_message = self._on_message

    # ── туслах ──
    def log(self, msg: str) -> None:
        if self.args.verbose:
            print(f"[{self.name}] {msg}", file=sys.stderr)

    def telemetry(self, **kv) -> None:
        self.c.publish(TOPIC_TELEMETRY, json.dumps(kv), qos=1)

    def state(self, st: str, **extra) -> None:
        self.log(f"төлөв → {st}")
        self.telemetry(fw_state=st, **extra)

    # ── MQTT callback-ууд ──
    def _on_connect(self, cl, userdata, flags, rc, properties=None):
        if rc != 0:
            print(f"[{self.name}] холбогдож чадсангүй: {rc}", file=sys.stderr)
            self.outcome = "CONNECT_FAILED"
            self.finished.set()
            return
        cl.subscribe(TOPIC_ATTR_RESP, qos=1)
        cl.subscribe(TOPIC_ATTR_PUSH, qos=1)
        cl.subscribe(TOPIC_FW_RESP, qos=1)
        # одоогийн суулгаастай хувилбараа мэдээлнэ
        self.telemetry(current_fw_title="cnc302-agent",
                       current_fw_version=self.current_version)
        cl.publish(TOPIC_ATTR_REQ.format(rid=1),
                   json.dumps({"sharedKeys": SHARED_KEYS}), qos=1)
        self.log("холбогдож, firmware мэдээлэл асуулаа")

    def _on_message(self, cl, userdata, msg):
        if msg.topic.startswith("v2/fw/response/"):
            self._on_chunk(msg)
            return
        try:
            data = json.loads(msg.payload)
        except Exception:  # noqa: BLE001
            return
        shared = data.get("shared", data)      # response нь {"shared":{...}}
        if "fw_version" in shared and shared.get("fw_version"):
            self._maybe_update(shared)

    def _maybe_update(self, shared: dict) -> None:
        version = str(shared.get("fw_version"))
        if version == self.current_version:
            self.log(f"хувилбар {version} аль хэдийн суусан")
            self.outcome = "NO_UPDATE"
            self.finished.set()
            return
        self.title = str(shared.get("fw_title", ""))
        self.version = version
        self.expect_size = int(shared.get("fw_size", 0))
        self.checksum = str(shared.get("fw_checksum", ""))
        self.algo = str(shared.get("fw_checksum_algorithm", "SHA256")).upper()
        self.buf = bytearray()
        self.t_start = time.time()
        self.log(f"шинэ firmware {self.title} {self.version} "
                 f"({self.expect_size} байт) — татаж эхэлж байна")
        self.state("DOWNLOADING")
        self._request_chunk(0)

    def _request_chunk(self, cid: int) -> None:
        self.c.publish(TOPIC_FW_REQ.format(rid=self.rid, cid=cid),
                       str(CHUNK_SIZE), qos=1)

    def _on_chunk(self, msg) -> None:
        parts = msg.topic.split("/")
        cid = int(parts[-1])
        self.buf.extend(msg.payload)
        if len(self.buf) < self.expect_size and len(msg.payload) > 0:
            self._request_chunk(cid + 1)
            return
        self._verify_and_install()

    # ── шалгах ба суулгах ──
    def _verify_and_install(self) -> None:
        self.state("DOWNLOADED")
        algo = {"SHA256": hashlib.sha256, "SHA384": hashlib.sha384,
                "SHA512": hashlib.sha512, "MD5": hashlib.md5}.get(
                    self.algo, hashlib.sha256)
        digest = algo(bytes(self.buf)).hexdigest()

        if self.checksum and digest.lower() != self.checksum.lower():
            self.log(f"ХЯНАЛТЫН НИЙЛБЭР ТААРАХГҮЙ: {digest} != {self.checksum}")
            self.state("FAILED", fw_error="checksum mismatch")
            self.outcome = "CHECKSUM_FAILED"
            self.t_end = time.time()
            self.finished.set()
            return

        self.state("VERIFIED")
        self.state("UPDATING")
        time.sleep(self.args.install_seconds)   # "суулгах" хугацааг дуурайна

        # Зориудаар амжилтгүй болгох (canary тараалтын туршилт)
        if random.random() < self.args.fail_rate:
            self.log("СУУЛГАЛТ АМЖИЛТГҮЙ — өмнөх хувилбар руу буцаж байна")
            self.state("FAILED", fw_error="install failed, rolled back")
            self.telemetry(current_fw_version=self.current_version,
                           rollback=True)
            self.outcome = "ROLLED_BACK"
        else:
            self.current_version = self.version
            self.state("UPDATED")
            self.telemetry(current_fw_title=self.title,
                           current_fw_version=self.current_version)
            self.outcome = "UPDATED"

        self.t_end = time.time()
        self.finished.set()

    # ── ажиллуулах ──
    def run(self) -> None:
        try:
            self.c.connect(self.args.host, self.args.port, keepalive=60)
        except Exception as exc:  # noqa: BLE001
            print(f"[{self.name}] {exc}", file=sys.stderr)
            self.outcome = "CONNECT_FAILED"
            self.finished.set()
            return
        self.c.loop_start()
        self.finished.wait(timeout=self.args.timeout)
        if not self.finished.is_set():
            self.outcome = "TIMEOUT"
        time.sleep(0.3)
        self.c.loop_stop()
        self.c.disconnect()

    @property
    def duration(self) -> float:
        return (self.t_end - self.t_start) if self.t_end else 0.0


def load_tokens(args: argparse.Namespace) -> list[tuple[str, str]]:
    if args.token:
        return [(args.token, "dev0000")]
    if not args.tokens_csv:
        print("--token эсвэл --tokens-csv аль нэгийг заана уу", file=sys.stderr)
        sys.exit(2)
    out = []
    with open(args.tokens_csv, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append((row["access_token"], row["name"]))
    return out[: args.devices] if args.devices else out


def main() -> int:
    p = argparse.ArgumentParser(description="ThingsBoard OTA агент")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1884,
                   help="ThingsBoard-ын MQTT порт (compose дээр 1884)")
    p.add_argument("--token", help="нэг төхөөрөмжийн access token")
    p.add_argument("--tokens-csv", help="provision.py-ийн гаргасан CSV")
    p.add_argument("--devices", type=int, default=0, help="CSV-ээс хэдийг авах")
    p.add_argument("--fail-rate", type=float, default=0.0,
                   help="суулгалт амжилтгүй болох магадлал 0..1")
    p.add_argument("--install-seconds", type=float, default=2.0)
    p.add_argument("--timeout", type=float, default=180.0)
    p.add_argument("--csv", help="үр дүнг CSV-д бичих")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    devices = [OtaDevice(tok, args, name) for tok, name in load_tokens(args)]
    print(f"→ {len(devices)} төхөөрөмж дээр OTA эхэлж байна "
          f"(fail-rate={args.fail_rate})…", file=sys.stderr)

    threads = [threading.Thread(target=d.run, daemon=True) for d in devices]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=args.timeout + 10)
    wall = time.time() - t0

    tally: dict[str, int] = {}
    for d in devices:
        tally[d.outcome] = tally.get(d.outcome, 0) + 1

    print(f"\n{'ТӨХӨӨРӨМЖ':<14}{'ҮР ДҮН':<18}{'ХУГАЦАА (с)':>12}")
    print("-" * 44)
    for d in devices:
        print(f"{d.name:<14}{d.outcome:<18}{d.duration:>12.1f}")
    print("-" * 44)
    for k, v in sorted(tally.items()):
        print(f"{k:<32}{v:>4}  ({100*v/len(devices):.0f}%)")
    ok = tally.get("UPDATED", 0)
    print(f"\nАмжилтын хувь: {100*ok/len(devices):.1f}%   "
          f"нийт хугацаа: {wall:.1f} сек")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["name", "outcome", "duration_s", "final_version"])
            for d in devices:
                w.writerow([d.name, d.outcome, round(d.duration, 2),
                            d.current_version])
        print(f"CSV: {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
