#!/usr/bin/env python3
"""
CNC302 — OTA КЛИЕНТ (төхөөрөмжийн тал).

Энэ бол Лаб 2-ын гол код. Firmware-ийг MQTT-ээр хэсэгчлэн татаж,
шалгаж, суулгаж, төлөвөө мэдээлнэ. Алдаа гарвал буцаана (rollback).

ПРОТОКОЛ (CNC302-ийн өөрийн, ил тод):

  сервер → төхөөрөмж   .../ota/offer
      {"fw_id","version","size","sha256","chunk_size","chunks"}

  төхөөрөмж → сервер   .../ota/request
      {"fw_id","chunk": N}

  сервер → төхөөрөмж   .../ota/chunk/N        (хоёртын өгөгдөл)

  төхөөрөмж → сервер   .../ota/state
      {"fw_id","version","state","progress","error"}

  ТӨЛӨВИЙН ДАРААЛАЛ:
      DOWNLOADING → DOWNLOADED → VERIFIED → UPDATING → UPDATED
                                     ↓            ↓
                                  FAILED     ROLLED_BACK

Хэрэглээ:
    python3 ota_agent.py --device dev0001
    python3 ota_agent.py --device dev0001 --fail-verify     # эвдрэл дуурайх
    python3 ota_agent.py --device dev0001 --fail-apply      # rollback дуурайх
    python3 ota_agent.py --device dev0001 --drop-rate 0.2   # сүлжээний алдагдал
    python3 ota_agent.py --device dev0001 --username dev0001 --password …   # EMQX authn
    python3 ota_agent.py --device pi3b-01 --port 8883 \
        --cafile certs/ca.crt --cert certs/pi3b-01.crt --key certs/pi3b-01.key  # mTLS

Pi 3B-ийн санамж:
    Нэг хэсэг = 4 KiB. 1 MiB firmware = 256 хэсэг. 100 Mbit сүлжээ, QoS 1
    → онолын хувьд секундэд хэдэн зуун хэсэг. Практикт брокерын
    round-trip нь хязгаарлагч болно — Лаб 2-т үүнийг хэмжинэ.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion


class OtaAgent:
    def __init__(self, args):
        self.a = args
        base = (f"cnc302/{args.site}/{args.area}/{args.line}/{args.device}")
        self.t_offer = f"{base}/ota/offer"
        self.t_request = f"{base}/ota/request"
        self.t_chunk = f"{base}/ota/chunk"
        self.t_state = f"{base}/ota/state"

        self.fw: dict | None = None
        self.buf: dict[int, bytes] = {}
        self.next_chunk = 0
        self.t0 = 0.0
        self.done = False
        self.rng = random.Random(1234)
        self.retries = 0
        self.last_request_at = 0.0

        self.c = mqtt.Client(CallbackAPIVersion.VERSION2,
                             client_id=f"ota-{args.device}-{os.getpid()}",
                             protocol=mqtt.MQTTv5)
        if args.username:
            self.c.username_pw_set(args.username, args.password)
        if args.cafile:
            # --cert/--key өгвөл mTLS (клиентийн сертификат), үгүй бол нэг талын TLS
            self.c.tls_set(ca_certs=args.cafile, certfile=args.cert,
                           keyfile=args.key)
        self.c.on_connect = self._on_connect
        self.c.on_message = self._on_message

    # ── төлөв мэдээлэх ────────────────────────────────────────────────────
    def report(self, state: str, **extra) -> None:
        msg = {"fw_id": (self.fw or {}).get("fw_id"),
               "version": (self.fw or {}).get("version"),
               "device": self.a.device, "state": state,
               "ts": int(time.time() * 1000), **extra}
        self.c.publish(self.t_state, json.dumps(msg), qos=1)
        prog = extra.get("progress", "")
        print(f"  [{state}] {prog}")

    # ── MQTT ──────────────────────────────────────────────────────────────
    # paho-mqtt 2.x, CallbackAPIVersion.VERSION2:
    #   on_connect(client, userdata, flags, reason_code, properties)
    def _on_connect(self, c, u, f, rc, p=None):
        if rc != 0:
            print(f"холбогдож чадсангүй rc={rc}")
            return
        c.subscribe([(self.t_offer, 1), (f"{self.t_chunk}/+", 1)])
        print(f"төхөөрөмж {self.a.device} — санал хүлээж байна…")

    def _on_message(self, c, u, msg):
        if msg.topic == self.t_offer:
            self._on_offer(msg.payload)
        elif msg.topic.startswith(self.t_chunk + "/"):
            self._on_chunk(int(msg.topic.rsplit("/", 1)[1]), msg.payload)

    # ── 1. Санал ──────────────────────────────────────────────────────────
    def _on_offer(self, payload: bytes) -> None:
        try:
            fw = json.loads(payload.decode())
        except (ValueError, UnicodeDecodeError):
            return
        if self.fw and self.fw.get("fw_id") == fw.get("fw_id") and not self.done:
            return                                        # давхардсан санал
        self.fw = fw
        self.buf.clear()
        self.next_chunk = 0
        self.retries = 0
        self.done = False
        self.t0 = time.time()
        print(f"\nсанал: v{fw['version']}  {fw['size']} байт  "
              f"{fw['chunks']} хэсэг × {fw['chunk_size']} B")
        self.report("DOWNLOADING", progress="0%")
        self._request(0)

    def _request(self, idx: int) -> None:
        self.last_request_at = time.time()
        self.c.publish(self.t_request,
                       json.dumps({"fw_id": self.fw["fw_id"], "chunk": idx}),
                       qos=1)

    # ── 2. Хэсэг хүлээн авах ──────────────────────────────────────────────
    def _on_chunk(self, idx: int, blob: bytes) -> None:
        if self.fw is None or self.done:
            return
        # Сүлжээний алдагдлыг дуурайх (--drop-rate)
        if self.a.drop_rate and self.rng.random() < self.a.drop_rate:
            print(f"  ✗ хэсэг {idx} алдагдлаа (дуурайлт)")
            return
        if idx != self.next_chunk:
            return                                        # дараалал зөрсөн
        self.buf[idx] = blob
        self.next_chunk += 1
        # Амжилттай хэсэг ирэхэд тоолуурыг тэглэнэ. Эс бөгөөс max_retries нь
        # НИЙТ алдагдлыг тоолж, урт татан авалт үргэлж унана.
        self.retries = 0
        total = self.fw["chunks"]
        if self.next_chunk % max(1, total // 10) == 0 or self.next_chunk == total:
            self.report("DOWNLOADING",
                        progress=f"{100 * self.next_chunk // total}%")
        if self.next_chunk < total:
            self._request(self.next_chunk)
        else:
            self._finish_download()

    # ── 3. Шалгах ─────────────────────────────────────────────────────────
    def _finish_download(self) -> None:
        data = b"".join(self.buf[i] for i in range(self.fw["chunks"]))
        dt = time.time() - self.t0
        kbps = len(data) / 1024 / dt if dt else 0
        print(f"  татаж дууслаа: {len(data)} байт, {dt:.1f} сек, {kbps:.0f} KiB/сек")
        self.report("DOWNLOADED", progress="100%", seconds=round(dt, 2),
                    kib_per_s=round(kbps, 1))

        digest = hashlib.sha256(data).hexdigest()
        if self.a.fail_verify:
            digest = "0" * 64                              # эвдрэл дуурайх
        if digest != self.fw["sha256"]:
            self.report("FAILED", error="sha256 таарахгүй",
                        expected=self.fw["sha256"][:16], got=digest[:16])
            print("  ✗ ШАЛГАЛТ УНАЛАА — суулгахгүй. Хуучин хувилбар хэвээр.")
            self.done = True
            return
        self.report("VERIFIED")

        # ── 4. Суулгах ────────────────────────────────────────────────────
        self.report("UPDATING")
        outdir = Path(self.a.out)
        outdir.mkdir(parents=True, exist_ok=True)
        backup = outdir / "previous.bin"
        current = outdir / "current.bin"
        vfile = outdir / "version.txt"
        old_version = vfile.read_text() if vfile.exists() else None
        if current.exists():
            backup.write_bytes(current.read_bytes())
        current.write_bytes(data)
        vfile.write_text(self.fw["version"])
        time.sleep(self.a.apply_seconds)

        if self.a.fail_apply:
            # Буцаалт: нөөцлөсөн хувилбар ба хувилбарын дугаарыг сэргээнэ
            if backup.exists():
                current.write_bytes(backup.read_bytes())
            else:
                current.unlink()                    # өмнө нь юу ч суугаагүй байсан
            if old_version is not None:
                vfile.write_text(old_version)
            else:
                vfile.unlink()
            self.report("ROLLED_BACK", error="суулгасны дараа ачаалж чадсангүй")
            print("  ↩ БУЦААЛАА — хуучин хувилбар сэргээгдлээ.")
        else:
            self.report("UPDATED", progress="100%",
                        total_seconds=round(time.time() - self.t0, 2))
            print(f"  ✓ ШИНЭЧЛЭГДЛЭЭ → v{self.fw['version']}")
        self.done = True

    # ── Ажиллуулах ────────────────────────────────────────────────────────
    def run(self) -> int:
        self.c.connect(self.a.host, self.a.port, keepalive=30)
        self.c.loop_start()
        t_end = time.time() + self.a.timeout
        while time.time() < t_end:
            time.sleep(0.25)
            # Хэсэг ирэхгүй бол дахин гуйна (алдагдлаас сэргэх)
            if (self.fw and not self.done and self.last_request_at
                    and time.time() - self.last_request_at > self.a.retry_after):
                self.retries += 1
                if self.retries > self.a.max_retries:
                    self.report("FAILED", error="дахин оролдлого дууслаа")
                    self.done = True
                    break
                print(f"  … хэсэг {self.next_chunk} ирсэнгүй, дахин гуйж байна "
                      f"({self.retries}/{self.a.max_retries})")
                self._request(self.next_chunk)
            if self.done and self.a.once:
                break
        time.sleep(0.5)
        self.c.loop_stop()
        self.c.disconnect()
        return 0 if self.done else 2


def main() -> int:
    p = argparse.ArgumentParser(description="CNC302 OTA клиент")
    p.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    p.add_argument("--site", default=os.getenv("SITE", "shutis"))
    p.add_argument("--area", default=os.getenv("AREA", "mhts"))
    p.add_argument("--line", default=os.getenv("LINE", "lab"))
    p.add_argument("--device", required=True)
    p.add_argument("--username", help="EMQX authn идэвхтэй үед (devices.csv-ээс)")
    p.add_argument("--password")
    p.add_argument("--cafile", help="TLS: CA сертификат (8883 порттой хамт)")
    p.add_argument("--cert", help="mTLS: төхөөрөмжийн сертификат")
    p.add_argument("--key", help="mTLS: төхөөрөмжийн хувийн түлхүүр")
    p.add_argument("--out", default="out/fw")
    p.add_argument("--timeout", type=float, default=180.0)
    p.add_argument("--retry-after", type=float, default=4.0)
    p.add_argument("--max-retries", type=int, default=10)
    p.add_argument("--apply-seconds", type=float, default=1.0)
    p.add_argument("--drop-rate", type=float, default=0.0,
                   help="хэсэг алдагдах магадлал (сүлжээний эвдрэл дуурайх)")
    p.add_argument("--fail-verify", action="store_true")
    p.add_argument("--fail-apply", action="store_true")
    p.add_argument("--once", action="store_true",
                   help="нэг шинэчлэлт хийгээд гарах")
    return OtaAgent(p.parse_args()).run()


if __name__ == "__main__":
    sys.exit(main())
