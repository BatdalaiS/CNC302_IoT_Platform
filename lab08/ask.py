#!/usr/bin/env python3
"""
CNC302 Лаб 8 — GenAI аналитик: байгалийн хэлээр цаг цувааны өгөгдөл асуух

Урсгал:
  асуулт (монгол/англи)
      ↓ Ollama (локал LLM, Pi дээр)
  SQL асуулга
      ↓ ХАМГААЛАЛТЫН ШҮҮЛТ  ← энэ хэсэг хамгийн чухал
  InfluxDB 3
      ↓ мөрүүд
      ↓ Ollama (хариу боловсруулах)
  байгалийн хэлээр хариулт

⚠ ГОЛ СУРГАМЖ: LLM бол ИТГЭМЖЛЭГДЭХГҮЙ оролт үүсгэгч. Түүний гаргасан
SQL-ийг шууд ажиллуулах нь хэрэглэгчийн оруулсан SQL-ийг шууд ажиллуулахтай
адил. Тиймээс `guard_sql()` функц заавал шаардлагатай.

  python3 ask.py "сүүлийн 6 цагт хамгийн их чичиргээтэй 5 төхөөрөмж аль нь вэ"
  python3 ask.py --show-sql "dev0001-ийн өнөөдрийн дундаж температур"
  python3 ask.py --dry-run "ямар нэг зүйл"        # LLM-гүй, шүүлтийг турших
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time

import httpx

SCHEMA_DOC = """
Хүснэгт: telemetry
  time            TIMESTAMP   — хэмжилтийн агшин
  site            VARCHAR     — байршил (ж: ulaanbaatar)
  area            VARCHAR     — талбай (ж: campus)
  line            VARCHAR     — шугам (ж: line01)
  device          VARCHAR     — төхөөрөмжийн ID (ж: dev0001)
  temperature     DOUBLE      — хэм, °C
  humidity        DOUBLE      — чийг, %
  vibration_rms   DOUBLE      — чичиргээний RMS

Хүснэгт: telemetry_1m   (1 минутын нэгтгэл)
  time, site, area, line, device,
  avg_temperature DOUBLE, min_temperature DOUBLE,
  max_temperature DOUBLE, samples BIGINT
"""

SYSTEM_PROMPT = f"""Чи бол InfluxDB 3 (SQL) дээр асуулга бичдэг туслах.
Доорх схемийг ашиглаж, хэрэглэгчийн асуултад тохирох ГАНЦ SQL SELECT
асуулга бич.

{SCHEMA_DOC}

ДҮРЭМ:
- Зөвхөн SELECT. INSERT/UPDATE/DELETE/DROP/CREATE/ALTER хориотой.
- Заавал LIMIT тавь (дээд тал нь 200).
- Хугацааны шүүлтэд: time > now() - INTERVAL '6 hours'
- Тайлбар, markdown, ``` бүү бич. ЗӨВХӨН SQL-ийг буцаа.
"""

ANSWER_PROMPT = """Чи бол IoT платформын аналитик туслах. Доорх өгөгдөлд
тулгуурлан хэрэглэгчийн асуултад МОНГОЛ хэлээр товч, тоон баримттай
хариул. Өгөгдөлд байхгүй зүйлийг БҮҮ зохио. Хэрэв өгөгдөл хоосон бол
"өгөгдөл олдсонгүй" гэж хэл.
"""

# ─────────────────────── ХАМГААЛАЛТЫН ШҮҮЛТ ───────────────────────

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|truncate|grant|revoke|"
    r"copy|attach|pragma|call|execute)\b", re.I)
MULTI_STMT = re.compile(r";\s*\S")


def guard_sql(sql: str, max_limit: int = 200) -> str:
    """
    LLM-ийн гаргасан SQL-ийг шалгана. Аюултай бол ValueError шиднэ.
    Энэ функц бол лабораторийн гол сургамж — LLM-д хэзээ ч бүү итгэ.
    """
    # Дараалал чухал: эхлээд markdown хашлагыг бүхэлд нь ав, дараа нь цэвэрлэ.
    sql = sql.strip()
    fence = re.match(r"^\s*```[a-zA-Z]*\s*(.*?)\s*```\s*$", sql, re.S)
    if fence:
        sql = fence.group(1)
    sql = sql.strip().strip("`").strip()
    sql = re.sub(r"^\s*(?:sql|SQL)\s*[\r\n]+", "", sql).strip()
    sql = sql.rstrip(";").strip()

    if not sql:
        raise ValueError("хоосон асуулга")
    if MULTI_STMT.search(sql + " "):
        raise ValueError("олон илэрхийлэл (;) хориотой")
    if not re.match(r"^\s*(select|with)\b", sql, re.I):
        raise ValueError(f"зөвхөн SELECT зөвшөөрнө: {sql[:60]}")
    if FORBIDDEN.search(sql):
        raise ValueError(f"хориотой түлхүүр үг илэрлээ: {sql[:80]}")
    if re.search(r"--|/\*", sql):
        raise ValueError("тайлбар (comment) хориотой")

    tables = set(re.findall(r"\bfrom\s+([a-zA-Z_][\w]*)", sql, re.I))
    tables |= set(re.findall(r"\bjoin\s+([a-zA-Z_][\w]*)", sql, re.I))
    allowed = {"telemetry", "telemetry_1m"}
    if not tables or not tables <= allowed:
        raise ValueError(f"зөвшөөрөгдөөгүй хүснэгт: {tables - allowed}")

    m = re.search(r"\blimit\s+(\d+)", sql, re.I)
    if not m:
        sql += f" LIMIT {max_limit}"
    elif int(m.group(1)) > max_limit:
        sql = re.sub(r"\blimit\s+\d+", f"LIMIT {max_limit}", sql, flags=re.I)
    return sql


# ─────────────────────────── Ollama ───────────────────────────

def ollama(base: str, model: str, system: str, prompt: str,
           timeout: float = 180) -> tuple[str, float]:
    t0 = time.time()
    r = httpx.post(f"{base.rstrip('/')}/api/generate",
                   json={"model": model, "system": system, "prompt": prompt,
                         "stream": False,
                         "options": {"temperature": 0.1, "num_predict": 400}},
                   timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", "").strip(), time.time() - t0


def influx_sql(base: str, db: str, q: str) -> list[dict]:
    r = httpx.post(f"{base.rstrip('/')}/api/v3/query_sql",
                   json={"db": db, "q": q, "format": "json"}, timeout=60)
    r.raise_for_status()
    return r.json()


# ─────────────────────────── main ───────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="GenAI аналитик (Ollama + InfluxDB)")
    p.add_argument("question", nargs="+")
    p.add_argument("--ollama", default="http://localhost:11434")
    p.add_argument("--model", default="qwen2.5:1.5b",
                   help="Pi дээр 3B-ээс дээш загвар хэт удаан")
    p.add_argument("--influx", default="http://localhost:8181")
    p.add_argument("--db", default="cnc302")
    p.add_argument("--show-sql", action="store_true")
    p.add_argument("--no-answer", action="store_true",
                   help="зөвхөн SQL ба мөрүүдийг харуулна")
    p.add_argument("--dry-run", action="store_true",
                   help="LLM дуудахгүй — шүүлтийг турших")
    p.add_argument("--json", help="үр дүнг JSON-д бичих")
    a = p.parse_args()
    question = " ".join(a.question)

    out = {"question": question, "model": a.model}

    if a.dry_run:
        print("── ХАМГААЛАЛТЫН ШҮҮЛТИЙН ТУРШИЛТ ──\n")
        cases = [
            "SELECT device, max(vibration_rms) FROM telemetry GROUP BY device",
            "select * from telemetry limit 5000",
            "SELECT * FROM telemetry; DROP TABLE telemetry",
            "DELETE FROM telemetry",
            "SELECT * FROM users",
            "SELECT * FROM telemetry -- аюултай тайлбар",
            "```sql\nSELECT count(*) FROM telemetry\n```",
        ]
        for c in cases:
            try:
                print(f"  ✓ ЗӨВШӨӨРӨВ  {guard_sql(c)[:70]}")
            except ValueError as exc:
                print(f"  ✗ ТАТГАЛЗАВ   {c[:44]!r}\n                {exc}")
        return 0

    # 1) Асуулт → SQL
    print(f"→ [1/3] SQL үүсгэж байна ({a.model})…", file=sys.stderr)
    raw_sql, t_gen = ollama(a.ollama, a.model, SYSTEM_PROMPT, question)
    out["raw_sql"] = raw_sql
    out["sql_generation_s"] = round(t_gen, 2)

    # 2) Шүүлт
    try:
        sql = guard_sql(raw_sql)
    except ValueError as exc:
        print(f"\n⛔ ШҮҮЛТ ТАТГАЛЗЛАА: {exc}", file=sys.stderr)
        print(f"   LLM-ийн гаргасан: {raw_sql[:200]}", file=sys.stderr)
        out["blocked"] = str(exc)
        if a.json:
            json.dump(out, open(a.json, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        return 1
    out["sql"] = sql
    if a.show_sql or a.no_answer:
        print(f"\nSQL ({t_gen:.1f}s):\n  {sql}\n")

    # 3) Гүйцэтгэх
    print("→ [2/3] Асуулга ажиллуулж байна…", file=sys.stderr)
    t0 = time.time()
    try:
        rows = influx_sql(a.influx, a.db, sql)
    except httpx.HTTPStatusError as exc:
        print(f"\n⛔ InfluxDB алдаа: {exc.response.text[:300]}", file=sys.stderr)
        out["db_error"] = exc.response.text[:500]
        return 2
    t_q = time.time() - t0
    out["rows"] = len(rows)
    out["query_s"] = round(t_q, 3)
    print(f"   {len(rows)} мөр, {t_q:.3f} сек", file=sys.stderr)

    if a.no_answer:
        for r in rows[:20]:
            print("  ", json.dumps(r, ensure_ascii=False))
        return 0

    # 4) Мөрүүд → байгалийн хэлээр хариулт
    print("→ [3/3] Хариулт боловсруулж байна…", file=sys.stderr)
    ctx = json.dumps(rows[:40], ensure_ascii=False, default=str)
    answer, t_ans = ollama(
        a.ollama, a.model, ANSWER_PROMPT,
        f"Асуулт: {question}\n\nSQL: {sql}\n\nҮр дүн (JSON):\n{ctx}")
    out["answer"] = answer
    out["answer_generation_s"] = round(t_ans, 2)

    print(f"\n{'═'*64}\n  {question}\n{'═'*64}")
    print(f"{answer}\n")
    print(f"  [SQL {t_gen:.1f}s · асуулга {t_q:.2f}s · хариу {t_ans:.1f}s "
          f"· нийт {t_gen+t_q+t_ans:.1f}s · {len(rows)} мөр]")

    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
