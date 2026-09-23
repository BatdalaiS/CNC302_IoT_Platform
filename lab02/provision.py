#!/usr/bin/env python3
"""
CNC302 — ТӨХӨӨРӨМЖ БҮРТГЭХ ХЭРЭГСЭЛ (registry үйлчилгээний клиент).

Хоёр загварыг харьцуулна:

  BULK (бөөнөөр)  — үйлдвэрээс гарахаас өмнө бүх төхөөрөмжийг бүртгэнэ.
                    + Урьдчилан хянагдана, нэвтрэлт бэлэн
                    − Ашиглагдахгүй байж болзошгүй мянган бүртгэл үлдэнэ,
                      нууц үг нь бүтээгдэхүүнд суух ёстой

  JIT (яг цагт нь) — төхөөрөмж анх залгагдахдаа өөрөө бүртгүүлнэ.
                    + Зөвхөн бодитоор ашиглагдсан нь бүртгэгдэнэ
                    − Бүртгүүлэх мөчид нь ХЭН БОЛОХЫГ нь батлах хэрэгтэй,
                      эс бөгөөс хэн ч флотод нэвтэрч болно

Лаб 2-т хоёуланг нь хийж, хугацааг хэмжиж, хяналтын асуултад хариулна.

Хэрэглээ:
    python3 provision.py bulk --count 50 --out out/devices.csv
    python3 provision.py jit  --device-id pi3b-01
    python3 provision.py list
    python3 provision.py revoke --device-id dev0007
    python3 provision.py cleanup --prefix dev
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import httpx

DEFAULT_URL = os.getenv("REGISTRY_URL", "http://localhost:8090")


def api(url: str, method: str, path: str, **kw):
    try:
        r = httpx.request(method, url.rstrip("/") + path, timeout=30.0, **kw)
    except httpx.HTTPError as e:
        sys.exit(f"✗ бүртгэлийн үйлчилгээнд хүрэхгүй байна ({url}): {e}\n"
                 f"  Зөөврийн компьютер дээр:  cd stack && make up")
    if r.status_code >= 400:
        sys.exit(f"✗ {method} {path} → {r.status_code}: {r.text[:300]}")
    return r.json()


# ─────────────────────────── bulk ───────────────────────────
def cmd_bulk(a) -> int:
    print(f"БӨӨНӨӨР бүртгэж байна: {a.count} төхөөрөмж, угтвар '{a.prefix}'…")
    t0 = time.perf_counter()
    res = api(a.url, "POST", "/devices",
              json={"prefix": a.prefix, "count": a.count, "label": a.label})
    dt = time.perf_counter() - t0

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["device_id", "username", "password", "emqx"])
        for d in res["devices"]:
            w.writerow([d["id"], d["id"], d.get("password", ""), d.get("emqx", "")])

    per = dt / max(1, res["created"]) * 1000
    print(f"✓ {res['created']} төхөөрөмж, {dt:.2f} сек "
          f"({per:.1f} мс/төхөөрөмж)")
    print(f"  нэвтрэлтийн мэдээлэл → {out}")
    print(f"  ⚠ ЭНЭ ФАЙЛ НУУЦ. .gitignore-д байгаа — Git-д БҮҮ оруул.")
    print(f"\n  ХЭМЖИЛТ (тайланд бич):  bulk, {a.count} ш, {dt:.2f} сек, "
          f"{per:.1f} мс/төх.")
    return 0


# ─────────────────────────── jit ───────────────────────────
def cmd_jit(a) -> int:
    print(f"JIT бүртгэл: {a.device_id}")
    t0 = time.perf_counter()
    res = api(a.url, "POST", "/devices/claim",
              json={"device_id": a.device_id, "secret": a.secret})
    dt = (time.perf_counter() - t0) * 1000
    print(f"✓ {res['id']}  нууц үг={res['password']}  ({dt:.1f} мс)")
    if res.get("note"):
        print(f"  тэмдэглэл: {res['note']}")
    print(f"\n  ХЯНАЛТЫН АСУУЛТ: энэ дуудлагад ямар ч баталгаа байхгүй.")
    print(f"  Хэн ч device_id сонгоод флотод нэвтэрч чадна. Үүнийг хэрхэн засах вэ?")
    print(f"  (Хариу: үйлдвэрийн X.509 сертификат — make_certs.sh-ийг үзнэ үү)")
    return 0


# ─────────────────────────── list / revoke ───────────────────────────
def cmd_list(a) -> int:
    res = api(a.url, "GET", f"/devices?limit={a.limit}"
                            + (f"&state={a.state}" if a.state else ""))
    devs = res["devices"]
    if not devs:
        print("(хоосон)")
        return 0
    print(f"{'ID':<14}{'төлөв':<14}{'хувилбар':<12}{'сүүлд харагдсан'}")
    print("-" * 60)
    for d in devs:
        seen = (time.strftime("%H:%M:%S", time.localtime(d["last_seen"]))
                if d.get("last_seen") else "—")
        print(f"{d['id']:<14}{d['state']:<14}{d['fw_version']:<12}{seen}")
    print(f"\nнийт {len(devs)}")
    return 0


def cmd_revoke(a) -> int:
    res = api(a.url, "DELETE", f"/devices/{a.device_id}")
    print(f"✓ {res['id']} хүчингүй боллоо (EMQX хэрэглэгч: {res['emqx']})")
    print(f"  Хөөсөн идэвхтэй холболт: {res.get('kicked')}")
    print("  EMQX authenticator идэвхтэй бол шинэ холболт татгалзагдана.")
    print("  ХЯНАЛТЫН АСУУЛТ: хэрэглэгчийг устгах нь яагаад ХОЛБОГДСОН session-ыг")
    print("  таслахгүй вэ? (Санамж: нэвтрэлтийг CONNECT пакетын үед л шалгадаг.)")
    return 0


def cmd_cleanup(a) -> int:
    res = api(a.url, "GET", "/devices?limit=2000")
    victims = [d["id"] for d in res["devices"] if d["id"].startswith(a.prefix)]
    if not victims:
        print("устгах зүйл алга")
        return 0
    print(f"{len(victims)} төхөөрөмжийг хүчингүй болгоно…")
    for d in victims:
        api(a.url, "DELETE", f"/devices/{d}")
    print(f"✓ {len(victims)} ширхэг")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="CNC302 төхөөрөмж бүртгэх хэрэгсэл")
    p.add_argument("--url", default=DEFAULT_URL,
                   help=f"бүртгэлийн үйлчилгээ (анхдагч: {DEFAULT_URL})")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("bulk", help="бөөнөөр бүртгэх")
    b.add_argument("--count", type=int, default=50)
    b.add_argument("--prefix", default="dev")
    b.add_argument("--label", default="cnc302-fleet")
    b.add_argument("--out", default="out/devices.csv")
    b.set_defaults(fn=cmd_bulk)

    j = sub.add_parser("jit", help="төхөөрөмж өөрөө бүртгүүлэх")
    j.add_argument("--device-id", required=True)
    j.add_argument("--secret", default="")
    j.set_defaults(fn=cmd_jit)

    l = sub.add_parser("list", help="жагсаалт")
    l.add_argument("--limit", type=int, default=50)
    l.add_argument("--state", choices=["provisioned", "active", "revoked"])
    l.set_defaults(fn=cmd_list)

    r = sub.add_parser("revoke", help="хүчингүй болгох")
    r.add_argument("--device-id", required=True)
    r.set_defaults(fn=cmd_revoke)

    c = sub.add_parser("cleanup", help="угтвараар бөөнөөр хүчингүй болгох")
    c.add_argument("--prefix", default="dev")
    c.set_defaults(fn=cmd_cleanup)

    a = p.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
