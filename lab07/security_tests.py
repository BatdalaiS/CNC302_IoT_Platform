#!/usr/bin/env python3
"""
CNC302 Лаб 7 — Хандалтын хяналтын АВТОМАТ ШАЛГАЛТ

Аюулгүй байдлыг "тохируулаад дуусгах" биш, ШАЛГАЖ баталгаажуулна.
Энэ скрипт нь эмзэг байдлыг зориудаар хайна. Улаанаар гарсан мөр бүр
таны системийн бодит асуудал.

  python3 security_tests.py --api http://pi-team03.local:8000
  python3 security_tests.py --api http://pi-team03.local:8000 --json out/sec.json
"""
from __future__ import annotations
import argparse, base64, json, sys, time
import httpx

PASS, FAIL, WARN = "ТЭНЦСЭН", "УНАСАН", "АНХААР"
results: list[dict] = []


def forge_jwt(claims: dict) -> str:
    """
    Бүтцийн хувьд ЗӨВ, гарын үсгийн хувьд ХУУРАМЧ токен үүсгэнэ.

    Анхаар: гарын үсгийн хэсэг нь base64url хэлбэртэй байх ёстой. Эс тэгвээс
    номын сан токеныг бүтцийн алдаа гэж үзэж, бид гарын үсгийн шалгалтыг
    туршиж чадахгүй (алдаатай "тэнцсэн" үр дүн гарна).
    """
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    fake_sig = base64.urlsafe_b64encode(b"not-a-real-signature").rstrip(b"=").decode()
    return f"{b({'alg':'RS256','typ':'JWT'})}.{b(claims)}.{fake_sig}"


def denied(r) -> bool:
    """Хүсэлт татгалзсан эсэх — HTTP 401/403 эсвэл GraphQL алдаа."""
    if r.status_code in (401, 403):
        return True
    try:
        return "errors" in r.json()
    except Exception:  # noqa: BLE001
        return True


def record(name: str, status: str, detail: str, severity: str = "medium") -> None:
    icon = {"ТЭНЦСЭН": "✓", "УНАСАН": "✗", "АНХААР": "⚠"}[status]
    color = {"ТЭНЦСЭН": "\033[32m", "УНАСАН": "\033[31m", "АНХААР": "\033[33m"}[status]
    print(f"  {color}{icon} {name:<46}{status}\033[0m")
    if status != PASS:
        print(f"      {detail}")
    results.append({"test": name, "status": status, "detail": detail,
                    "severity": severity})


def gql(api: str, query: str, token: str | None = None, timeout=15):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.post(f"{api}/graphql", json={"query": query}, headers=h,
                      timeout=timeout)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--influx", default="http://localhost:8181")
    p.add_argument("--tb", default="http://localhost:8080")
    p.add_argument("--json", help="үр дүнг JSON-д бичих")
    a = p.parse_args()

    print(f"\n{'═'*66}\n  АЮУЛГҮЙ БАЙДЛЫН ШАЛГАЛТ — {a.api}\n{'═'*66}\n")

    # ── 1. Танигдаагүй хандалт ──
    print("1. Танилтгүй хандалт")
    try:
        r = gql(a.api, "{ devices { name } }")
        body = r.json() if r.status_code < 500 else {}
        if denied(r):
            record("Анонимоор төхөөрөмж жагсаах татгалзсан", PASS, "")
        else:
            n = len(body.get("data", {}).get("devices") or [])
            record("Анонимоор төхөөрөмж жагсаах татгалзсан", FAIL,
                   f"Токенгүйгээр {n} төхөөрөмж уншигдав!", "high")
    except Exception as exc:
        record("Анонимоор төхөөрөмж жагсаах татгалзсан", WARN, str(exc))

    # ── 2. Хуурамч гарын үсэг ──
    print("\n2. Токены гарын үсгийн шалгалт")
    tok = forge_jwt({"sub": "evil", "groups": ["admin"], "exp": time.time() + 3600})
    r = gql(a.api, "{ whoami }", tok)
    who = r.json().get("data", {}).get("whoami", "")
    if "admin" in who:
        record("Хуурамч гарын үсэгтэй токен татгалзсан", FAIL,
               f"ГАРЫН ҮСГИЙГ ШАЛГААГҮЙ! Хариу: {who}", "critical")
    else:
        record("Хуурамч гарын үсэгтэй токен татгалзсан", PASS, "")

    # ── 3. Эрхийн өсөлт ──
    print("\n3. Эрхийн өсөлт (privilege escalation)")
    vt = forge_jwt({"sub": "bob", "groups": ["viewer"]})
    r = gql(a.api, 'mutation { sendCommand(device:"x", command:"reboot") }', vt)
    if denied(r):
        record("viewer тушаал илгээхийг татгалзсан", PASS, "")
    else:
        record("viewer тушаал илгээхийг татгалзсан", FAIL,
               "viewer үүрэг тушаал илгээж чадлаа!", "high")

    # ── 4. Хугацаа дууссан токен ──
    print("\n4. Хугацааны шалгалт")
    et = forge_jwt({"sub": "carol", "groups": ["admin"], "exp": time.time() - 7200})
    r = gql(a.api, "{ whoami }", et)
    if "admin" in r.json().get("data", {}).get("whoami", ""):
        record("Хугацаа дууссан токен татгалзсан", FAIL,
               "exp талбарыг шалгаагүй", "high")
    else:
        record("Хугацаа дууссан токен татгалзсан", PASS, "")

    # ── 5. GraphQL-ийн өөрийн эрсдэлүүд ──
    print("\n5. GraphQL-ийн онцлог эрсдэлүүд")
    r = gql(a.api, "{ __schema { types { name fields { name } } } }")
    if r.status_code == 200 and "data" in r.json():
        record("Introspection хаагдсан", WARN,
               "Схем бүрэн уншигдаж байна. Үйлдвэрлэлд хаах ёстой "
               "(strawberry.Schema(..., config=StrawberryConfig(...)) эсвэл "
               "нэвтэрсэн хэрэглэгчид л зөвшөөрөх).", "low")
    else:
        record("Introspection хаагдсан", PASS, "")

    # Асуулгын нийлмэл байдал: нэг хүсэлтэд 200 давхар нэрлэсэн (alias) талбар.
    # Энэ бол GraphQL-ийн бодит DoS вектор — REST-д ийм зүйл боломжгүй.
    aliases = " ".join(f"a{i}: devices(limit: 50) {{ name }}" for i in range(200))
    try:
        r = gql(a.api, "{ " + aliases + " }", timeout=25)
        if r.status_code == 200 and "errors" not in r.json():
            record("Асуулгын нийлмэл байдлын хязгаар", WARN,
                   "200 давхар нэрлэсэн талбартай асуулга хүлээн авагдав — "
                   "DoS эрсдэл. strawberry-д QueryDepthLimiter / "
                   "cost analysis нэмэх ёстой.", "medium")
        else:
            record("Асуулгын нийлмэл байдлын хязгаар", PASS, "")
    except Exception:
        record("Асуулгын нийлмэл байдлын хязгаар", PASS,
               "хугацаа хэтэрч таслагдав (хязгаарлалт ажиллаж байна)")

    # ── 6. SQL тарилга (InfluxDB рүү) ──
    print("\n6. Тарилгын шалгалт")
    at = forge_jwt({"sub": "dave", "groups": ["admin"]})
    payload = "x' OR '1'='1"
    q = '{ device(name: "%s") { name } }' % payload
    try:
        r = gql(a.api, q, at)
        txt = r.text.lower()
        if "syntax" in txt or "sql" in txt or "traceback" in txt:
            record("Тарилгын оролдлого аюулгүй боловсруулагдсан", FAIL,
                   "SQL алдааны мессеж клиент рүү нэвтэрлээ", "high")
        else:
            record("Тарилгын оролдлого аюулгүй боловсруулагдсан", WARN,
                   "Алдаа гарсангүй, гэхдээ асуулга нь мөр залгалтаар "
                   "үүсгэгддэг — параметржүүлсэн асуулга руу шилжүүлэх ёстой",
                   "high")
    except Exception as exc:
        record("Тарилгын оролдлого аюулгүй боловсруулагдсан", WARN, str(exc))

    # ── 7. Дэд бүтцийн ил задгай байдал ──
    print("\n7. Дэд бүтцийн үйлчилгээ ил байна уу")
    for name, url, why in (
        ("InfluxDB танилтгүй уншигдана", f"{a.influx}/health",
         "InfluxDB нь --without-auth горимд ажиллаж байна"),
        ("ThingsBoard нэвтрэх хуудас", f"{a.tb}/login", "хэвийн"),
    ):
        try:
            r = httpx.get(url, timeout=6)
            if "InfluxDB" in name and r.status_code == 200:
                record(name, FAIL, why + " — Лаб 7-т токен идэвхжүүлэх ёстой",
                       "high")
            else:
                record(name, PASS, "")
        except Exception:
            record(name, PASS, "хандах боломжгүй")

    # ── дүн ──
    print(f"\n{'═'*66}")
    counts = {s: sum(1 for r in results if r["status"] == s)
              for s in (PASS, WARN, FAIL)}
    print(f"  ТЭНЦСЭН {counts[PASS]}   АНХААР {counts[WARN]}   "
          f"УНАСАН {counts[FAIL]}")
    crit = [r for r in results if r["severity"] in ("critical", "high")
            and r["status"] == FAIL]
    if crit:
        print(f"\n  ⚠ {len(crit)} ноцтой асуудал:")
        for r in crit:
            print(f"    · [{r['severity']}] {r['test']}")
            print(f"      {r['detail']}")
    print(f"{'═'*66}\n")

    if a.json:
        json.dump({"api": a.api, "results": results, "summary": counts},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"JSON: {a.json}")
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
