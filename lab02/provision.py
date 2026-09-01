#!/usr/bin/env python3
"""
CNC302 Лаб 2 — Төхөөрөмжийн provisioning (ThingsBoard REST API)

Хоёр стратегийг харьцуулна:

  bulk : Бүх төхөөрөмжийг урьдчилан платформ дээр үүсгэж, итгэмжлэлийг
         үйлдвэрлэлийн шатанд төхөөрөмжид суулгана. Урьдчилан таамаглах
         боломжтой, гэхдээ ашиглагдахгүй итгэмжлэл олноор үлддэг.

  jit  : Төхөөрөмж анх холбогдох үедээ өөрийгөө бүртгүүлнэ (just-in-time).
         Хэрэглэгдэхгүй итгэмжлэл үүсэхгүй, гэхдээ бүртгэлийн түлхүүр
         (provision key) алдагдвал хэн ч төхөөрөмж нэмж чадна.

Жишээ:
  python provision.py --url http://localhost:8080 --mode bulk --count 20
  python provision.py --url http://localhost:8080 --mode bulk --count 20 --csv bulk.csv
  python provision.py --url http://localhost:8080 --list
  python provision.py --url http://localhost:8080 --cleanup
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time

import requests

TIMEOUT = 20


class TB:
    """ThingsBoard REST API-ийн нимгэн бүрхүүл."""

    def __init__(self, url: str, user: str, password: str) -> None:
        self.url = url.rstrip("/")
        self.s = requests.Session()
        r = self.s.post(
            f"{self.url}/api/auth/login",
            json={"username": user, "password": password},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        self.s.headers["X-Authorization"] = f"Bearer {r.json()['token']}"

    def create_device(self, name: str, profile: str | None = None) -> dict:
        body: dict = {"name": name, "type": "default", "label": "CNC302 lab device"}
        if profile:
            body["deviceProfileId"] = {"id": profile, "entityType": "DEVICE_PROFILE"}
        r = self.s.post(f"{self.url}/api/device", json=body, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()

    def credentials(self, device_id: str) -> dict:
        r = self.s.get(
            f"{self.url}/api/device/{device_id}/credentials", timeout=TIMEOUT
        )
        r.raise_for_status()
        return r.json()

    def list_devices(self, page_size: int = 200) -> list[dict]:
        r = self.s.get(
            f"{self.url}/api/tenant/devices",
            params={"pageSize": page_size, "page": 0},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json().get("data", [])

    def delete_device(self, device_id: str) -> None:
        self.s.delete(f"{self.url}/api/device/{device_id}", timeout=TIMEOUT)

    def set_server_attributes(self, device_id: str, attrs: dict) -> None:
        self.s.post(
            f"{self.url}/api/plugins/telemetry/DEVICE/{device_id}/SERVER_SCOPE",
            json=attrs,
            timeout=TIMEOUT,
        )


def provision_bulk(tb: TB, prefix: str, count: int) -> list[dict]:
    """Бүх төхөөрөмжийг урьдчилан үүсгэнэ."""
    rows = []
    for i in range(count):
        name = f"{prefix}{i:04d}"
        t0 = time.perf_counter()
        dev = tb.create_device(name)
        cred = tb.credentials(dev["id"]["id"])
        dt = (time.perf_counter() - t0) * 1000
        tb.set_server_attributes(
            dev["id"]["id"],
            {"provisioned_at": int(time.time() * 1000), "provision_mode": "bulk"},
        )
        rows.append(
            {
                "name": name,
                "device_id": dev["id"]["id"],
                "access_token": cred["credentialsId"],
                "mode": "bulk",
                "ms": round(dt, 1),
            }
        )
        print(f"  [{i+1}/{count}] {name}  {dt:6.1f} мс", file=sys.stderr)
    return rows


def provision_jit(tb: TB, prefix: str, count: int, delay: float) -> list[dict]:
    """
    Just-in-time: төхөөрөмж 'ажилд орох' үедээ л үүснэ.
    Энд бид төхөөрөмжүүд санамсаргүй хугацаанд ирж байгааг дуурайна.
    """
    rows = []
    for i in range(count):
        time.sleep(delay)
        name = f"{prefix}{i:04d}"
        t0 = time.perf_counter()
        dev = tb.create_device(name)
        cred = tb.credentials(dev["id"]["id"])
        dt = (time.perf_counter() - t0) * 1000
        tb.set_server_attributes(
            dev["id"]["id"],
            {"provisioned_at": int(time.time() * 1000), "provision_mode": "jit"},
        )
        rows.append(
            {
                "name": name,
                "device_id": dev["id"]["id"],
                "access_token": cred["credentialsId"],
                "mode": "jit",
                "ms": round(dt, 1),
            }
        )
        print(f"  [{i+1}/{count}] {name}  {dt:6.1f} мс (JIT)", file=sys.stderr)
    return rows


def summarize(rows: list[dict]) -> None:
    if not rows:
        return
    ms = [r["ms"] for r in rows]
    ms_sorted = sorted(ms)
    p95 = ms_sorted[min(int(0.95 * (len(ms_sorted) - 1)), len(ms_sorted) - 1)]
    print(
        f"\nДүн ({rows[0]['mode']}): {len(rows)} төхөөрөмж\n"
        f"  дундаж : {statistics.fmean(ms):7.1f} мс\n"
        f"  медиан : {statistics.median(ms):7.1f} мс\n"
        f"  p95    : {p95:7.1f} мс\n"
        f"  дээд   : {max(ms):7.1f} мс\n"
        f"  нийт   : {sum(ms)/1000:7.2f} сек",
        file=sys.stderr,
    )


def main() -> int:
    p = argparse.ArgumentParser(description="ThingsBoard төхөөрөмжийн provisioning")
    p.add_argument("--url", default="http://localhost:8080")
    p.add_argument("--user", default="tenant@thingsboard.org")
    p.add_argument("--password", default="tenant")
    p.add_argument("--mode", choices=["bulk", "jit"], default="bulk")
    p.add_argument("--prefix", default="dev")
    p.add_argument("--count", type=int, default=10)
    p.add_argument("--jit-delay", type=float, default=0.5,
                   help="JIT горимд төхөөрөмж хоорондын завсар (сек)")
    p.add_argument("--csv", help="үр дүн ба итгэмжлэлийг CSV-д бичих")
    p.add_argument("--list", action="store_true", help="одоо байгаа төхөөрөмжүүд")
    p.add_argument("--cleanup", action="store_true",
                   help="--prefix-ээр эхэлсэн БҮХ төхөөрөмжийг устгах")
    args = p.parse_args()

    tb = TB(args.url, args.user, args.password)

    if args.list:
        devs = tb.list_devices()
        print(f"{len(devs)} төхөөрөмж:")
        for d in devs:
            print(f"  {d['name']:<16} {d['id']['id']}")
        return 0

    if args.cleanup:
        devs = [d for d in tb.list_devices() if d["name"].startswith(args.prefix)]
        print(f"{len(devs)} төхөөрөмж устгана ('{args.prefix}*')…", file=sys.stderr)
        for d in devs:
            tb.delete_device(d["id"]["id"])
            print(f"  устгав: {d['name']}", file=sys.stderr)
        return 0

    print(f"→ {args.mode} горимоор {args.count} төхөөрөмж үүсгэж байна…",
          file=sys.stderr)
    t0 = time.perf_counter()
    rows = (provision_bulk(tb, args.prefix, args.count) if args.mode == "bulk"
            else provision_jit(tb, args.prefix, args.count, args.jit_delay))
    wall = time.perf_counter() - t0

    summarize(rows)
    print(f"  бодит хугацаа: {wall:7.2f} сек", file=sys.stderr)

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nCSV: {args.csv}  ← ЭНЭ ФАЙЛД ИТГЭМЖЛЭЛ БАЙНА, Git-д оруулахгүй!",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
