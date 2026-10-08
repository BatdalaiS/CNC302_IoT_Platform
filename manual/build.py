#!/usr/bin/env python3
"""
CNC302 — Markdown зааврыг LaTeX болгон хөрвүүлэх.

  python3 build.py            # chapters/*.tex үүсгэнэ
  python3 build.py --pdf      # + xelatex-ээр хөрвүүлнэ
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile

SRC = os.environ.get("CNC302_SRC", "..")
OUT = "chapters"

# (эх файл, гарах файл, бүлгийн гарчиг, төрөл)
CHAPTERS = [
    ("README.md",                 "00-intro.tex",      "Гарын авлагын танилцуулга", "chapter"),
    ("SETUP.md",                  "01-setup.tex",      "Ажлын орчны бэлтгэл",       "chapter"),
    ("edge/README.md",            "01b-edge.tex",      "Ирмэгийн давхарга — лавлах", "chapter"),
    ("lab01/README.md",           "02-lab01.tex",      None, "chapter"),
    ("lab02/README.md",           "03-lab02.tex",      None, "chapter"),
    ("lab03/README.md",           "04-lab03.tex",      None, "chapter"),
    ("lab04/README.md",           "05-lab04.tex",      None, "chapter"),
    ("lab05/README.md",           "06-lab05.tex",      None, "chapter"),
    ("lab06/README.md",           "07-lab06.tex",      None, "chapter"),
    ("lab07/README.md",           "08-lab07.tex",      None, "chapter"),
    ("lab08/README.md",           "09-lab08.tex",      None, "chapter"),
    ("docs/report-template.md",   "10-report.tex",     "Тайлангийн загвар",          "appendix"),
    ("docs/troubleshooting.md",   "11-trouble.tex",    "Түгээмэл алдаа ба шийдэл",   "appendix"),
    ("docs/resource-budget.md",   "12-resources.tex",  "Нөөцийн төсөв",              "appendix"),
    ("lab08/k3s/README.md",       "13-k3s.tex",        "K3s манифестууд",            "appendix"),
]

# DejaVu фонтод байхгүй тэмдэгтүүдийг орлуулна
GLYPH_MAP = {
    # Ажлын байрны тэмдэглэгээ. DejaVu-д эдгээр эможи БАЙХГҮЙ тул хэвлэмэл
    # хувилбарт товчилсон текстээр орлуулна (Markdown-д эможи хэвээр).
    # Терминалын шошго "[💻 Ubuntu]", "[🥧 Pi-1]" — давхар хаалт гаргахгүйн тулд
    # хаалттай хэлбэрийг ЭХЛЭЭД орлуулна (dict-ийн дараалал хадгалагдана).
    "[💻 ": "[ЗК · ",
    "[🥧 Pi": "[Pi",
    "[🥧 ": "[Pi · ",
    "💻": "[ЗК]",       # зөөврийн компьютер (үүлний давхарга)
    "🥧": "[Pi]",       # Raspberry Pi 3B (ирмэгийн давхарга)
    "🖥": "[VM]",       # Лаб 8: K3s server-ийн VirtualBox VM
    "⭐": "",           # хүснэгтийн тэмдэглэгээ — доор текстээр орлоно
    "⛔": "СТОП:",
    "✅": "✓",          # "Шалгах" — newunicodechar-аар DejaVu Sans-аас
    "❌": "✗",
    "💡": "☞",
    "˅": "▼",
    "🔒": "",
    "�": "",       # эвдэрсэн кодчилолын үлдэгдэл
    "☒": "[x]",
    "☐": "[ ]",
    " ": " ",
    "​": "",
    "️": "",            # variation selector-16
    "️": "",
}


def preprocess(md: str) -> str:
    """Markdown-ийг pandoc-т өгөхийн өмнө цэвэрлэнэ."""
    # GitHub-д зориулсан толгой (badge, Actions-ийн заавар) нь хэвлэмэл
    # хувилбарт хэрэггүй. `<!-- GitHub толгой -->`-оос эхний `# ` гарчиг
    # хүртэлх хэсгийг бүхэлд нь хасна.
    md = re.sub(r"^<!--\s*GitHub толгой\s*-->.*?(?=^# )", "", md,
                flags=re.S | re.M)
    # ⭐ тэмдэгтэй хүснэгтийн гарчгийг текстээр тэмдэглэнэ
    md = re.sub(r"^(###\s+.*?)\s*⭐\s*$", r"\1 (ГОЛ ХҮСНЭГТ)", md, flags=re.M)
    for k, v in GLYPH_MAP.items():
        md = md.replace(k, v)

    # <details>/<summary> → энгийн дэд гарчиг
    md = re.sub(
        r"<details>\s*\n<summary>(.*?)</summary>\s*\n(.*?)\n</details>",
        lambda m: "**" + re.sub(r"</?b>", "", m.group(1)).strip() + "**\n\n"
                  + m.group(2),
        md, flags=re.S)

    # Зураг: Markdown дахь `../docs/img/X.svg` (эсвэл `docs/img/X.svg`)
    # холбоосыг convert_figures()-ийн үүсгэсэн `figures/X.pdf` руу заалгана.
    md = re.sub(r"\]\((?:\.\./)?docs/img/([A-Za-z0-9_-]+)\.svg\)",
                r"](figures/\1.pdf)", md)

    # H1 гарчгийг авна (бүлгийн нэр болгоно)
    lines = md.split("\n")
    title = None
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            title = ln[2:].strip()
            lines[i] = ""
            break
    md = "\n".join(lines)

    # Markdown-ийн `---` тусгаарлагчийг устгана (LaTeX-д хэрэггүй)
    md = re.sub(r"^---\s*$", "", md, flags=re.M)

    # ````  ... ```mermaid ... ```  ... ```` хэлбэрийн үүрлэсэн блокийг
    # нэг энгийн блок болгож хураана (дотоод хашлагыг хасна)
    md = re.sub(r"````\s*\n```mermaid\s*\n(.*?)\n```\s*\n````",
                lambda m: "```\n" + m.group(1) + "\n```", md, flags=re.S)
    md = md.replace("```mermaid", "```")

    # Бөглөх зориулалттай урт доогуур зураасыг LaTeX-ийн шугам болгоно.
    # ЧУХАЛ: кодын блок дотор хөндөхгүй — тэнд текст нь тэр чигтээ хэвлэгдэнэ.
    md = _replace_outside_code(md, _underscores_to_rule)

    return title, md


FENCE = re.compile(r"^(\s*)(`{3,}|~{3,})", re.M)


def _replace_outside_code(md: str, fn):
    """Кодын блокоос ГАДНА байгаа хэсэгт л fn-ийг хэрэглэнэ."""
    out, in_code, fence = [], False, ""
    for line in md.split("\n"):
        m = FENCE.match(line)
        if m:
            tok = m.group(2)
            if not in_code:
                in_code, fence = True, tok
            elif tok[0] == fence[0] and len(tok) >= len(fence):
                in_code, fence = False, ""
            out.append(line)
            continue
        out.append(line if in_code else fn(line))
    return "\n".join(out)


def _underscores_to_rule(line: str) -> str:
    """
    ______  → бөглөх зурвас.
    Мөр бүхэлдээ зураас бол хуудасны өргөнөөр (\hrulefill), эс бөгөөс богино.
    """
    stripped = line.strip()
    if len(stripped) >= 6 and set(stripped) == {"_"}:
        return "`\\par\\noindent\\rule{\\linewidth}{0.4pt}\\par`{=latex}"
    return re.sub(r"_{6,}", "`\\rule{1.5cm}{0.4pt}`{=latex}", line)


def convert_figures(src: str) -> int:
    """docs/img/*.svg → figures/*.pdf (вектор хэвээр, cairosvg)."""
    img = os.path.join(src, "docs", "img")
    if not os.path.isdir(img):
        return 0
    try:
        import cairosvg
    except ImportError:
        print("  ! cairosvg алга:  pip install cairosvg", file=sys.stderr)
        return 0
    os.makedirs("figures", exist_ok=True)
    n = 0
    for name in sorted(os.listdir(img)):
        if not name.endswith(".svg"):
            continue
        dst = os.path.join("figures", name[:-4] + ".pdf")
        cairosvg.svg2pdf(url=os.path.join(img, name), write_to=dst)
        n += 1
    return n


def pandoc(md: str, top: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                     encoding="utf-8") as f:
        f.write(md)
        path = f.name
    try:
        r = subprocess.run(
            ["pandoc", path, "-f",
             "markdown+pipe_tables+backtick_code_blocks+fenced_code_attributes"
             "+raw_attribute+raw_tex-smart",
             "-t", "latex",
             "--highlight-style=tango",
             f"--top-level-division={top}",
             "--wrap=preserve"],
            capture_output=True, text=True, check=True)
        return r.stdout
    finally:
        os.unlink(path)


def postprocess(tex: str) -> str:
    """pandoc-ийн гаралтыг гоё болгоно."""
    # Урт хүснэгтийг жижигрүүлнэ
    tex = tex.replace("\\begin{longtable}", "\\begingroup\\scriptsize\\begin{longtable}")
    tex = tex.replace("\\end{longtable}", "\\end{longtable}\\endgroup")

    # Хүснэгтийн толгойг тод болгоно (pandoc аль хэдийн хийдэг, давхардлыг арилгана)
    tex = tex.replace("\\toprule\\noalign{}", "\\toprule")
    tex = tex.replace("\\midrule\\noalign{}", "\\midrule")
    tex = tex.replace("\\bottomrule\\noalign{}", "\\bottomrule")
    tex = tex.replace("\\endhead\\noalign{}", "\\endhead")

    # \texttt{...} доторх урт танигчийг доогуур зураасаар таслах боломжтой болгоно
    # (жишээ: EMQX_LISTENERS__TCP__DEFAULT__MAX_CONNECTIONS хүснэгтийн нүдэнд багтахгүй)
    def brk(m):
        inner = m.group(1)
        if inner.count("\\_") >= 2:
            inner = inner.replace("\\_", "\\_\\allowbreak{}")
        # Урт URL / зам нь мөрөнд багтахгүй тул тусгаарлагчийн ДАРАА таслах
        # боломж нэмнэ (жишээ: http://influxdb:8181/api/v3/write_lp?db=…).
        # \allowbreak нь зөвхөн БОЛОМЖ өгнө — шаардлагагүй бол таслахгүй.
        if len(inner) > 16:
            for sep in ("/", "?", "\\&", "=", ":", ".", "\\textbackslash{}"):
                inner = inner.replace(sep, sep + "\\allowbreak{}")
            if "\\_\\allowbreak" not in inner:
                inner = inner.replace("\\_", "\\_\\allowbreak{}")
        return "\\texttt{" + inner + "}"
    # pandoc нь <, >, [, ], … тэмдэгтийг \textless{}, \textgreater{}, {[}, {]}, \ldots{}
    # болгодог — эдгээр хаалт ч таарах ёстой, эс бөгөөс урт texttt алгасагдана.
    TT_INNER = r"(?:[^{}]|\\[{}_&%#$]|\\text(?:less|greater)\{\}|\\ldots\{\}|\\textbackslash\{\}|\{\[\}|\{\]\})*"
    tex = re.sub(r"\\texttt\{(" + TT_INNER + r")\}", brk, tex)
    # \texttt{a}/\texttt{b}/… дарааллын "/"-ийн дараа таслах боломж
    tex = tex.replace("}/\\texttt{", "}/\\allowbreak\\texttt{")

    # \href{url}{бичвэр}: Эх сурвалжийн хүснэгтийн нарийн нүдэнд урт холбоосын
    # бичвэр (жишээ: github.com/raspberrypi/documentation) багтахгүй. URL-ийг
    # хөндөхгүйгээр ЗӨВХӨН харагдах бичвэрт таслах боломж нэмнэ.
    def hbrk(m):
        url, txt = m.group(1), m.group(2)
        if len(txt) > 20:
            for sep in ("/", ".", "\\_"):     # "-" БИШ: '---' (—) хуваагдана
                txt = txt.replace(sep, sep + "\\allowbreak{}")
        return "\\href{" + url + "}{" + txt + "}"
    tex = re.sub(r"\\href\{([^{}]*)\}\{((?:[^{}]|\\[{}_&%#$])*)\}", hbrk, tex)

    # \tightlist-ийг хэвээр үлдээнэ (preamble-д тодорхойлсон)
    # Хоосон догол мөрийг цэгцлэнэ
    tex = re.sub(r"\n{4,}", "\n\n\n", tex)
    return tex


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", action="store_true")
    ap.add_argument("--src", default=SRC)
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    print(f"Эх сурвалж: {os.path.abspath(a.src)}\n")
    nfig = convert_figures(a.src)
    print(f"  ✓ {nfig} зураг → figures/*.pdf\n")

    for src, dst, forced_title, top in CHAPTERS:
        path = os.path.join(a.src, src)
        if not os.path.exists(path):
            print(f"  ! олдсонгүй: {path}", file=sys.stderr)
            continue
        md = open(path, encoding="utf-8").read()
        title, md = preprocess(md)
        title = forced_title or title or dst
        body = postprocess(pandoc(md, "chapter"))
        header = f"% Автоматаар үүсгэсэн — эх файл: {src}\n\\chapter{{{title}}}\n\n"
        open(os.path.join(OUT, dst), "w", encoding="utf-8").write(header + body)
        n = len(body.splitlines())
        print(f"  ✓ {src:<28} → {OUT}/{dst:<18} ({n:4d} мөр)  {title}")

    if a.pdf:
        print("\n→ xelatex ажиллуулж байна (3 удаа)…")
        for i in range(3):
            r = subprocess.run(
                ["xelatex", "-interaction=nonstopmode", "-halt-on-error",
                 "main.tex"], capture_output=True, text=True)
            if r.returncode != 0:
                print(f"\n✗ {i+1}-р ажиллуулалт амжилтгүй:\n", file=sys.stderr)
                tail = [l for l in r.stdout.splitlines()
                        if l.startswith("!") or "l." in l[:4] or "Error" in l]
                print("\n".join(tail[-40:]), file=sys.stderr)
                return 1
            print(f"  {i+1}/3 OK")
        print("\n✓ main.pdf бэлэн")
    return 0


if __name__ == "__main__":
    sys.exit(main())
