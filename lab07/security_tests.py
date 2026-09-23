#!/usr/bin/env python3
"""
CNC302 Лаб 7 — Хандалтын хяналтын АВТОМАТ ШАЛГАЛТ

Аюулгүй байдлыг "тохируулаад дуусгах" биш, ШАЛГАЖ баталгаажуулна.
Энэ скрипт нь эмзэг байдлыг зориудаар хайна. Улаанаар гарсан мөр бүр
таны системийн бодит асуудал.

Бүх үйлчилгээ ҮҮЛНИЙ давхаргад (зөөврийн компьютер) ажиллана: GraphQL API
:8000, бүртгэл (registry) :8090, InfluxDB :8181. Pi 3B дээр зөвхөн ирмэгийн
mosquitto ба агент байгаа тул энд шалгах зүйл байхгүй.

  python3 security_tests.py --api http://localhost:8000
  python3 security_tests.py --api http://localhost:8000 \
      --influx http://localhost:8181 --registry http://localhost:8090 \
      --json lab07/out/security-before.json

ХҮЛЭЭГДЭХ ҮР ДҮН (засварын өмнө): ЯГ ХОЁР ноцтой асуудал — хоёулаа
`decode_token()`-ы санаатай эмзэг байдлаас үүдэлтэй (гарын үсэг ба
хугацаа шалгагдаагүй).
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


def record(name: str, status: str, detail: str, severity: str = "medium",
           deliberate: bool = False) -> None:
    """
    deliberate=True гэдэг нь `graphql-api/main.py` дотор ЗОРИУДААР үлдээсэн
    эмзэг байдлыг шалгаж буй тест. Дэд бүтцийн тохиргооны олдвороос
    (InfluxDB, registry) ялгаж дүгнэхэд хэрэгтэй.
    """
    icon = {"ТЭНЦСЭН": "✓", "УНАСАН": "✗", "АНХААР": "⚠"}[status]
    color = {"ТЭНЦСЭН": "\033[32m", "УНАСАН": "\033[31m", "АНХААР": "\033[33m"}[status]
    print(f"  {color}{icon} {name:<46}{status}\033[0m")
    if status != PASS:
        print(f"      {detail}")
    results.append({"test": name, "status": status, "detail": detail,
                    "severity": severity, "deliberate": deliberate})


def gql(api: str, query: str, token: str | None = None, timeout=15):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return httpx.post(f"{api}/graphql", json={"query": query}, headers=h,
                      timeout=timeout)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://localhost:8000")
    p.add_argument("--influx", default="http://localhost:8181")
    # ThingsBoard-ыг Лаб 2-ын өөрсдийн бүртгэл орлосон (:8090)
    p.add_argument("--registry", default="http://localhost:8090")
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
               f"ГАРЫН ҮСГИЙГ ШАЛГААГҮЙ! Хариу: {who}", "critical",
               deliberate=True)
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
               "exp талбарыг шалгаагүй", "high", deliberate=True)
    else:
        record("Хугацаа дууссан токен татгалзсан", PASS, "")

    # ── 5. GraphQL-ийн өөрийн эрсдэлүүд ──
    print("\n5. GraphQL-ийн онцлог эрсдэлүүд")
    r = gql(a.api, "{ __schema { types { name fields { name } } } }")
    # Анхаар: хаагдсан үед ч хариунд `"data": null` + `errors` ирнэ —
    # тиймээс түлхүүр байгаа эсэхийг биш, СХЕМ ирсэн эсэхийг шалгана.
    if r.status_code == 200 and (r.json().get("data") or {}).get("__schema"):
        record("Introspection хаагдсан", WARN,
               "Схем бүрэн уншигдаж байна. Үйлдвэрлэлд хаах ёстой "
               "(strawberry.extensions.DisableIntrospection эсвэл "
               "нэвтэрсэн хэрэглэгчид л зөвшөөрөх).", "low", deliberate=True)
    else:
        record("Introspection хаагдсан", PASS, "")

    # Асуулгын нийлмэл байдал: нэг хүсэлтэд 200 давхар нэрлэсэн (alias) талбар.
    # Энэ бол GraphQL-ийн бодит DoS вектор — REST-д ийм зүйл боломжгүй.
    #
    # Анхаар: RBAC-д татгалзагдах талбар (devices) ашиглавал шалгалт "тэнцсэн"
    # гэж БУРУУ дүгнэнэ — `decode_token` засагдсаны дараа хуурамч токен 401
    # авч, хязгаар байхгүй ч PASS гарна. Тиймээс эрх шаарддаггүй `whoami`-г
    # 200 удаа нэрлэнэ: энэ нь зөвхөн GraphQL-ийн ВАЛИДАЦИЙН хязгаарыг
    # (MaxAliasesLimiter / MaxTokensLimiter) шалгана, токен ба registry-ээс
    # хамаарахгүй. Бодит DoS-д `whoami`-ийн оронд `devices(limit:50)` байна.
    aliases = " ".join(f"a{i}: whoami" for i in range(200))
    try:
        r = gql(a.api, "{ " + aliases + " }", None, timeout=25)
        if r.status_code == 200 and "errors" not in r.json():
            record("Асуулгын нийлмэл байдлын хязгаар", WARN,
                   "200 давхар нэрлэсэн талбартай асуулга хүлээн авагдав — "
                   "DoS эрсдэл. strawberry.extensions-ийн MaxAliasesLimiter / "
                   "MaxTokensLimiter (+ QueryDepthLimiter) нэмэх ёстой.",
                   "medium", deliberate=True)
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

    # 7.1 InfluxDB — --without-auth горим (Zero Trust-ийн илэрхий зөрчил)
    try:
        r = httpx.get(f"{a.influx}/health", timeout=6)
        if r.status_code == 200:
            record("InfluxDB танилтгүй уншигдана", FAIL,
                   "InfluxDB нь --without-auth горимд ажиллаж байна "
                   "— Лаб 7-т токен идэвхжүүлэх ёстой", "high")
        else:
            record("InfluxDB танилтгүй уншигдана", PASS, "")
    except Exception:
        record("InfluxDB танилтгүй уншигдана", PASS, "хандах боломжгүй")

    # 7.2 Бүртгэл (registry) — ThingsBoard-ыг орлосон өөрсдийн үйлчилгээ.
    #     Лаб 2-т ЗОРИУДААР нээлттэй үлдээсэн: JIT `claim` нь хуваалцсан
    #     нууцгүйгээр ажиллана. Энэ бол мэдэгдэж буй цоорхой тул АНХААР
    #     зэрэглэлтэй — "ноцтой хоёр" жагсаалтад орохгүй, гэхдээ тайланд
    #     заавал бичигдэнэ.
    try:
        r = httpx.get(f"{a.registry}/devices", timeout=6)
        if r.status_code == 200:
            n = len(r.json().get("devices", []))
            record("Бүртгэл (registry) танилтгүй уншигдана", WARN,
                   f"Токенгүйгээр {n} төхөөрөмжийн бүртгэл уншигдав "
                   f"({a.registry}/devices). Бүртгэлийн API-д API түлхүүр "
                   f"эсвэл mTLS нэмэх ёстой (Лаб 2-ын хяналтын асуулт).",
                   "medium")
        else:
            record("Бүртгэл (registry) танилтгүй уншигдана", PASS, "")
    except Exception:
        record("Бүртгэл (registry) танилтгүй уншигдана", PASS,
               "хандах боломжгүй")

    # ── дүн ──
    print(f"\n{'═'*66}")
    counts = {s: sum(1 for r in results if r["status"] == s)
              for s in (PASS, WARN, FAIL)}
    print(f"  ТЭНЦСЭН {counts[PASS]}   АНХААР {counts[WARN]}   "
          f"УНАСАН {counts[FAIL]}")
    crit = [r for r in results if r["severity"] in ("critical", "high")
            and r["status"] == FAIL]
    intended = [r for r in crit if r["deliberate"]]
    infra = [r for r in crit if not r["deliberate"]]
    if intended:
        print(f"\n  ⚠ САНААТАЙ ЭМЗЭГ БАЙДАЛ — {len(intended)} ширхэг "
              f"(graphql-api/main.py, `decode_token`):")
        for r in intended:
            print(f"    · [{r['severity']}] {r['test']}")
            print(f"      {r['detail']}")
        if len(intended) != 2:
            print("    ⚠ Засварын өмнө энэ тоо ЯГ 2 байх ёстой. Өөр тоо гарвал "
                  "шалгалт эсвэл API буруу ажиллаж байна.")
    else:
        print("\n  ✓ Санаатай эмзэг байдал илрээгүй — засвар ажиллаж байна.")
    if infra:
        print(f"\n  ⚠ Дэд бүтцийн ноцтой олдвор — {len(infra)} ширхэг "
              f"(код биш, тохиргоо):")
        for r in infra:
            print(f"    · [{r['severity']}] {r['test']}")
            print(f"      {r['detail']}")
    print(f"{'═'*66}\n")

    if a.json:
        json.dump({"api": a.api, "results": results, "summary": counts,
                   "deliberate_criticals": len(intended),
                   "infra_criticals": len(infra)},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print(f"JSON: {a.json}")
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
