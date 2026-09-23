#!/usr/bin/env python3
"""
CNC302 — гарын авлагын зургуудыг үүсгэх.

    python3 docs/img/make_figures.py          # бүх SVG-г энэ хавтаст бичнэ
    python3 docs/img/make_figures.py --png    # + урьдчилан харах PNG (cairosvg)

Зураг бүр ЭНЭ скриптээс гардаг. SVG-г гараар засахгүй — энд засаад дахин
ажиллуулна. Ингэснээр өнгө, фонт, сумны хэв маяг бүх зурагт нэг байна.

Фонт: DejaVu Sans (кирилл үсэгтэй, LaTeX гарын авлагатай ижил).
"""
from __future__ import annotations

import argparse
import html
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent

# ── Өнгө (гарын авлагын preamble.tex-ийн өнгөтэй нийцүүлсэн) ──────────────────
INK = "#1F2937"        # үндсэн бичвэр
MUTED = "#5B6474"      # туслах бичвэр
LINE = "#374151"       # сум
GRID = "#D1D5DB"
CLOUD_FILL, CLOUD_STROKE = "#EAF0FA", "#2E5496"     # зөөврийн компьютер (үүл)
EDGE_FILL, EDGE_STROKE = "#E8F4EC", "#2E7D4F"       # Raspberry Pi 3B (ирмэг)
NEUTRAL_FILL, NEUTRAL_STROKE = "#FFFFFF", "#8A94A6"
WARN_FILL, WARN = "#FEF3E2", "#B45309"
BAD_FILL, BAD = "#FDECEC", "#B91C1C"
OK = "#15803D"
VM_FILL, VM_STROKE = "#F3EEFA", "#6B4FA0"            # K3s server VM

FONT = "DejaVu Sans, Arial, sans-serif"
MONO = "DejaVu Sans Mono, monospace"


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def tw(s: str, size: float = 13, mono: bool = False) -> float:
    """Бичвэрийн өргөний ойролцоо тооцоо (DejaVu Sans)."""
    return len(s) * size * (0.60 if mono else 0.58)


class Fig:
    def __init__(self, w: int, h: int, title: str):
        self.w, self.h, self.title = w, h, title
        self.parts: list[str] = []

    # ── примитивүүд ──────────────────────────────────────────────────────────
    def rect(self, x, y, w, h, fill=NEUTRAL_FILL, stroke=NEUTRAL_STROKE,
             rx=6, sw=1.4, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=13, color=INK, anchor="middle", weight="normal",
             mono=False, italic=False):
        fam = MONO if mono else FONT
        st = ' font-style="italic"' if italic else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" '
            f'fill="{color}" text-anchor="{anchor}" font-weight="{weight}"{st}>'
            f'{esc(s)}</text>')

    def lines(self, x, y, rows, size=13, color=INK, anchor="middle", gap=None,
              weight="normal", mono=False):
        gap = gap or size * 1.35
        for i, r in enumerate(rows):
            self.text(x, y + i * gap, r, size, color, anchor, weight, mono)

    def box(self, x, y, w, h, title, sub=(), fill=NEUTRAL_FILL,
            stroke=NEUTRAL_STROKE, tsize=13, ssize=11, mono_sub=False, dash=None):
        """Гарчиг + дэд мөрүүдтэй хайрцаг (голд нь байрлуулна)."""
        self.rect(x, y, w, h, fill, stroke, dash=dash)
        n = 1 + len(sub)
        block = tsize * 1.25 + (len(sub) * ssize * 1.35)
        ty = y + (h - block) / 2 + tsize * 0.95
        self.text(x + w / 2, ty, title, tsize, INK, weight="bold")
        for i, s in enumerate(sub):
            self.text(x + w / 2, ty + tsize * 0.35 + (i + 1) * ssize * 1.35, s,
                      ssize, MUTED, mono=mono_sub)

    def group(self, x, y, w, h, label, fill, stroke, lsize=14, dash=None):
        """Том бүлэг (машин / давхарга) — зүүн дээд буланд шошго."""
        self.rect(x, y, w, h, fill, stroke, rx=10, sw=2, dash=dash)
        self.text(x + 14, y + 22, label, lsize, stroke, anchor="start",
                  weight="bold")

    def arrow(self, x1, y1, x2, y2, label=None, color=LINE, sw=1.6, dash=None,
              both=False, lpos=0.5, loff=-7, lsize=11, lcolor=None,
              lanchor="middle", mono=False):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        mid = f"a{color.strip('#')}"
        # orient="auto-start-reverse" нь эхлэлийн сумыг өөрөө эргүүлдэг тул
        # ижил marker-ийг хоёр үзүүрт хэрэглэнэ.
        ms = f' marker-start="url(#{mid})"' if both else ""
        self.parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" '
            f'stroke-width="{sw}"{d} marker-end="url(#{mid})"{ms}/>')
        self._markers.add(color)
        if label:
            lx = x1 + (x2 - x1) * lpos
            ly = y1 + (y2 - y1) * lpos + loff
            self.text(lx, ly, label, lsize, lcolor or color, lanchor, mono=mono)

    def path(self, d, color=LINE, sw=1.6, dash=None, arrow=True, fill="none"):
        da = f' stroke-dasharray="{dash}"' if dash else ""
        mid = f"a{color.strip('#')}"
        me = f' marker-end="url(#{mid})"' if arrow else ""
        if arrow:
            self._markers.add(color)
        self.parts.append(f'<path d="{d}" fill="{fill}" stroke="{color}" '
                          f'stroke-width="{sw}"{da}{me}/>')

    def pill(self, x, y, s, fill, stroke, size=11, color=None, mono=True):
        w = tw(s, size, mono) + 14
        self.rect(x - w / 2, y - size - 3, w, size + 9, fill, stroke, rx=9, sw=1.1)
        self.text(x, y + 1, s, size, color or stroke, mono=mono)
        return w

    def raw(self, s: str):
        self.parts.append(s)

    # ── бичих ────────────────────────────────────────────────────────────────
    _markers: set

    def __post_init__(self):
        pass

    def svg(self) -> str:
        defs = []
        for c in sorted(self._markers):
            mid = f"a{c.strip('#')}"
            defs.append(
                f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" '
                f'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                f'<path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
            f'height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
            f'font-family="{FONT}">\n'
            f'<title>{esc(self.title)}</title>\n'
            f'<defs>{"".join(defs)}</defs>\n'
            f'<rect width="100%" height="100%" fill="#FFFFFF"/>\n'
            + "\n".join(self.parts) + "\n</svg>\n")


def new(w, h, title) -> Fig:
    f = Fig(w, h, title)
    f._markers = set()
    return f


def legend(f: Fig, x, y, items):
    """items: [(fill, stroke, label)]"""
    for fill, stroke, label in items:
        f.rect(x, y - 10, 14, 12, fill, stroke, rx=3, sw=1.2)
        f.text(x + 20, y, label, 11, MUTED, anchor="start")
        x += 26 + tw(label, 11)


# ═══════════════════════════════════════════════════════════════════════════
#  1. Хоёр давхаргат архитектур
# ═══════════════════════════════════════════════════════════════════════════
def fig_architecture() -> Fig:
    f = new(900, 500, "Хоёр давхаргат архитектур")

    # Мэдрэгч / флот
    f.box(20, 205, 130, 70, "Төхөөрөмжүүд", ("виртуал флот,", "мэдрэгч"))

    # Pi
    f.group(180, 40, 250, 380, "Raspberry Pi 3B — ирмэг", EDGE_FILL, EDGE_STROKE)
    f.text(194, 80, "1 GB RAM · 4×Cortex-A53 · microSD", 11, MUTED, "start")
    f.box(205, 100, 200, 70, "edge_agent.py", ("venv · UNS нийтлэгч", "LiteRT дүгнэлт (Лаб 6)"))
    f.box(205, 200, 200, 95, "Mosquitto 2.0", ("локал брокер :1883", "гүүр (bridge) → үүл",
                                                 "дараалал: RAM"), stroke=EDGE_STROKE)
    f.box(205, 330, 200, 60, "microSD", ("persistence: autosave 60 с",), dash="4 3")
    f.arrow(305, 170, 305, 200)
    f.arrow(305, 295, 305, 330, dash="4 3")
    f.arrow(150, 240, 205, 240, "MQTT", loff=-8)

    # Laptop
    f.group(580, 40, 300, 420, "Зөөврийн компьютер — үүл", CLOUD_FILL, CLOUD_STROKE)
    f.text(594, 80, "Docker Compose · stack/", 11, MUTED, "start")
    f.box(600, 100, 125, 56, "registry", (":8090 · OTA",))
    f.box(735, 100, 125, 56, "Dex + GraphQL", (":5556 · :8000",), tsize=12)
    f.box(600, 185, 260, 64, "EMQX 5.8", ("MQTT :1883 · mTLS :8883 · :18083",),
          stroke=CLOUD_STROKE)
    f.box(600, 280, 125, 56, "Node-RED", (":1880 · Лаб 5",))
    f.box(735, 280, 125, 56, "Ollama", (":11434 · Лаб 8",))
    f.box(600, 365, 125, 56, "InfluxDB 3", (":8181",))
    f.box(735, 365, 125, 56, "Grafana", (":3000",))
    f.text(730, 446, "Лаб 8: K3s server — VirtualBox VM", 11, VM_STROKE)
    f.arrow(662, 156, 662, 185, both=True)
    f.arrow(662, 249, 662, 280)
    f.arrow(662, 336, 662, 365)
    f.arrow(725, 393, 735, 393)

    # Bridge
    f.arrow(405, 228, 600, 208, color=EDGE_STROKE, sw=2.6)
    f.text(500, 182, "MQTT гүүр · QoS 1", 12, EDGE_STROKE, weight="bold")
    f.text(500, 199, "out: cnc302/<site>/#", 10.5, MUTED, mono=True)
    f.arrow(600, 232, 405, 262, color=CLOUD_STROKE, sw=1.4, dash="5 3")
    f.text(515, 280, "in: …/cmd · config · ota/#", 10.5, MUTED, mono=True)
    f.text(500, 330, "LAN · 100 Mb/s", 12, INK, weight="bold")
    f.text(500, 346, "өгсөх урсгал (uplink)", 11, MUTED)

    legend(f, 20, 488, [(EDGE_FILL, EDGE_STROKE, "ирмэг (Pi 3B)"),
                        (CLOUD_FILL, CLOUD_STROKE, "үүл (зөөврийн компьютер)"),
                        (NEUTRAL_FILL, NEUTRAL_STROKE, "тасархай = диск")])
    return f


# ═══════════════════════════════════════════════════════════════════════════
#  2. Хэмжилтийн гурван зам
# ═══════════════════════════════════════════════════════════════════════════
def fig_three_paths() -> Fig:
    f = new(900, 430, "Хэмжилтийн гурван зам")
    f.text(450, 26, "qos_latency.py нэг процесс дотор нийтэлж, хүлээж авна → хоёр машины цагийн зөрүү ордоггүй",
           12, MUTED)

    lanes = [("А. loopback", 50, "сүлжээгүй — Pi-гийн CPU ба брокер л"),
             ("Б. LAN", 170, "Pi → Ethernet → EMQX → Pi"),
             ("В. гүүр", 290, "Pi mosquitto → гүүр → EMQX → --sub-host")]
    for name, y, note in lanes:
        f.text(20, y + 38, name, 14, INK, "start", "bold")
        f.text(20, y + 56, note, 10.5, MUTED, "start")

    # columns
    f.group(250, 40, 290, 360, "Raspberry Pi 3B", EDGE_FILL, EDGE_STROKE, 13)
    f.group(620, 40, 260, 360, "Зөөврийн компьютер", CLOUD_FILL, CLOUD_STROKE, 13)

    # A
    f.box(265, 70, 120, 56, "qos_latency", ("pub + sub",), mono_sub=False)
    f.box(405, 70, 120, 56, "mosquitto", ("localhost:1883",), stroke=EDGE_STROKE)
    f.arrow(385, 90, 405, 90)
    f.arrow(405, 108, 385, 108)

    # B
    f.box(265, 190, 120, 56, "qos_latency", ("pub + sub",))
    f.box(690, 190, 120, 56, "EMQX", ("$CLOUD_HOST:1883",), stroke=CLOUD_STROKE)
    f.arrow(385, 208, 690, 208, "PUBLISH", lpos=0.5)
    f.arrow(690, 230, 385, 230, "хүлээн авах", lpos=0.5, loff=16)

    # C
    f.box(265, 310, 120, 56, "qos_latency", ("--sub-host",))
    f.box(405, 310, 120, 56, "mosquitto", ("гүүр",), stroke=EDGE_STROKE)
    f.box(690, 310, 120, 56, "EMQX", ("захиалагч",), stroke=CLOUD_STROKE)
    f.arrow(385, 326, 405, 326)
    f.arrow(525, 326, 690, 326, "гүүр · QoS 1", color=EDGE_STROKE, sw=2.2)
    f.path("M 690 352 L 600 352 L 600 390 L 325 390 L 325 366", color=CLOUD_STROKE)
    f.text(470, 384, "--sub-host $CLOUD_HOST", 10.5, CLOUD_STROKE, mono=True)

    f.text(450, 422, "p50 нь дундаж зан төлөв, p99 нь хэрэглэгчийн мэдрэх хамгийн муу тохиолдол — гол тоо нь p99",
           11.5, WARN)
    return f


# ═══════════════════════════════════════════════════════════════════════════
#  3. OTA төлөвийн машин + мессежийн дараалал
# ═══════════════════════════════════════════════════════════════════════════
def fig_ota_states() -> Fig:
    f = new(900, 520, "OTA протокол ба төлөвийн машин")

    # ── Дээд хэсэг: дарааллын диаграм ──
    f.text(20, 26, "А. Мессежийн дараалал (UNS: cnc302/…/<device>/ota/…)", 13, INK, "start", "bold")
    sx, dx = 230, 670
    f.box(sx - 100, 40, 200, 40, "registry (сервер)", (), stroke=CLOUD_STROKE, fill=CLOUD_FILL)
    f.box(dx - 110, 40, 220, 40, "ota_agent (төхөөрөмж)", (), stroke=EDGE_STROKE, fill=EDGE_FILL)
    f.raw(f'<line x1="{sx}" y1="80" x2="{sx}" y2="262" stroke="{GRID}" stroke-width="1.4" stroke-dasharray="4 4"/>')
    f.raw(f'<line x1="{dx}" y1="80" x2="{dx}" y2="262" stroke="{GRID}" stroke-width="1.4" stroke-dasharray="4 4"/>')
    y = 104
    steps = [
        (sx, dx, "ota/offer  {fw_id, version, size, sha256, chunks}"),
        (dx, sx, "ota/request  {fw_id, chunk: 0}"),
        (sx, dx, "ota/chunk/0  ‹4 KiB хоёртын›"),
        (dx, sx, "ota/request  {chunk: 1}  … N-1 хүртэл давтана"),
        (dx, sx, "ota/state  {state, progress, error}"),
    ]
    for a, b, lab in steps:
        f.arrow(a, y, b, y, lab, lsize=11, mono=True, lcolor=INK)
        y += 36
    f.text(dx + 12, 176, "хэсэг ирэхгүй бол", 10.5, WARN, "start")
    f.text(dx + 12, 190, "--retry-after сек-ийн дараа", 10.5, WARN, "start")
    f.text(dx + 12, 204, "дахин гуйна", 10.5, WARN, "start")

    # ── Доод хэсэг: төлөвийн машин ──
    f.text(20, 300, "Б. Төхөөрөмжийн төлөв", 13, INK, "start", "bold")
    Y = 330
    states = [("DOWNLOADING", 20), ("DOWNLOADED", 195), ("VERIFIED", 370),
              ("UPDATING", 545), ("UPDATED", 720)]
    for name, x in states:
        col = OK if name == "UPDATED" else CLOUD_STROKE
        fill = "#E7F5EC" if name == "UPDATED" else "#FFFFFF"
        f.box(x, Y, 150, 44, name, (), fill=fill, stroke=col, tsize=12)
    for i in range(len(states) - 1):
        x1 = states[i][1] + 150
        f.arrow(x1, Y + 22, states[i + 1][1], Y + 22)

    f.box(195, Y + 104, 150, 44, "FAILED", (), fill=BAD_FILL, stroke=BAD, tsize=12)
    f.box(545, Y + 104, 150, 44, "ROLLED_BACK", (), fill=WARN_FILL, stroke=WARN, tsize=12)
    f.arrow(270, Y + 44, 270, Y + 104, color=BAD)
    f.text(280, Y + 70, "sha256 таарахгүй", 11, BAD, "start")
    f.text(280, Y + 84, "→ суулгахгүй", 11, BAD, "start")
    f.arrow(620, Y + 44, 620, Y + 104, color=WARN)
    f.text(630, Y + 70, "ачаалагдсангүй", 11, WARN, "start")
    f.text(630, Y + 84, "→ previous.bin сэргээнэ", 11, WARN, "start")
    f.text(95, Y + 66, "хэсэг бүрийг", 10.5, MUTED)
    f.text(95, Y + 80, "дарааллаар татна", 10.5, MUTED)
    f.text(450, 505, "Canary: эхлээд 5–20% төхөөрөмжид → бүгд UPDATED бол /rollout/{id}/promote → бусдад", 11.5, INK)
    return f


# ═══════════════════════════════════════════════════════════════════════════
#  4. QoS 0 / 1 / 2 пакет солилцоо
# ═══════════════════════════════════════════════════════════════════════════
def fig_qos_flows() -> Fig:
    f = new(900, 400, "QoS 0, 1, 2")
    cols = [
        ("QoS 0 — at most once", "хамгийн ихдээ нэг удаа", 20,
         [("→", "PUBLISH")], "алдагдаж болно · давхардахгүй"),
        ("QoS 1 — at least once", "дор хаяж нэг удаа", 315,
         [("→", "PUBLISH (Packet ID)"), ("←", "PUBACK")],
         "алдагдахгүй · давхардаж болно (DUP)"),
        ("QoS 2 — exactly once", "яг нэг удаа", 610,
         [("→", "PUBLISH (Packet ID)"), ("←", "PUBREC"),
          ("→", "PUBREL"), ("←", "PUBCOMP")],
         "алдагдахгүй · давхардахгүй · хамгийн удаан"),
    ]
    for title, gloss, x, msgs, note in cols:
        w = 270
        f.rect(x, 20, w, 350, "#FAFBFD", GRID, rx=10)
        f.text(x + w / 2, 46, title, 13.5, INK, weight="bold")
        f.text(x + w / 2, 64, gloss, 11, MUTED)
        s, r = x + 55, x + w - 60
        f.box(s - 42, 80, 84, 30, "илгээгч", (), tsize=11)
        f.box(r - 52, 80, 104, 30, "хүлээн авагч", (), tsize=11)
        for xx in (s, r):
            f.raw(f'<line x1="{xx}" y1="110" x2="{xx}" y2="300" stroke="{GRID}" '
                  f'stroke-width="1.3" stroke-dasharray="4 4"/>')
        yy = 140
        for d, lab in msgs:
            a, b = (s, r) if d == "→" else (r, s)
            col = CLOUD_STROKE if d == "→" else EDGE_STROKE
            f.arrow(a, yy, b, yy + 14, lab, color=col, lsize=11, mono=True, lcolor=col)
            yy += 40
        f.text(x + w / 2, 330, note, 11, WARN if "алдагдаж" in note else INK)
        f.text(x + w / 2, 350, f"{len(msgs)} пакет", 11, MUTED)
    f.text(450, 392, "Гэрээ нь НЭГ hop-д (клиент ↔ брокер) хамаарна; гүүр мессежийг өөрийн QoS-оор (out 1) дахин нийтэлнэ — MQTT 5.0 §4.3",
           11, MUTED)
    return f


FIGURES = {
    "fig-architecture": fig_architecture,
    "fig-three-paths": fig_three_paths,
    "fig-ota-states": fig_ota_states,
    "fig-qos-flows": fig_qos_flows,
}


# ═══════════════════════════════════════════════════════════════════════════
#  5. Unified Namespace-ийн шатлал
# ═══════════════════════════════════════════════════════════════════════════
def fig_uns_tree() -> Fig:
    f = new(900, 440, "Unified Namespace")
    levels = [("угтвар", "cnc302"), ("site", "shutis"), ("area", "mhts"),
              ("line", "lab"), ("device", "pi3b-01")]
    x0, y0, dy = 40, 40, 58
    for i, (lvl, val) in enumerate(levels):
        x = x0 + i * 36
        y = y0 + i * dy
        f.text(x, y + 20, lvl, 11, MUTED, "start")
        w = tw(val, 13, True) + 26
        f.rect(x + 70, y, w, 30, CLOUD_FILL if i < 4 else EDGE_FILL,
               CLOUD_STROKE if i < 4 else EDGE_STROKE, rx=6)
        f.text(x + 70 + w / 2, y + 20, val, 13, INK, mono=True)
        if i:
            px = x0 + (i - 1) * 36 + 84
            f.path(f"M {px} {y - dy + 30} L {px} {y + 15} L {x + 70} {y + 15}",
                   color=LINE, arrow=False)

    # channels
    ch = [("telemetry", "ирмэг → үүл", "хэмжилт"),
          ("health", "ирмэг → үүл", "темп, RAM, throttle"),
          ("status", "ирмэг → үүл", "retained · LWT"),
          ("anomaly", "ирмэг → үүл", "зөвхөн онцгой"),
          ("bridge/state", "ирмэг → үүл", "1 / 0"),
          ("cmd", "үүл → ирмэг", "команд"),
          ("config", "үүл → ирмэг", "тохиргоо"),
          ("ota/…", "хоёр тал", "Лаб 2")]
    cx = 470
    f.text(cx, 30, "channel (суваг)", 12, MUTED, "start", "bold")
    dev_x, dev_y = x0 + 4 * 36 + 84, y0 + 4 * dy + 30
    for i, (name, d, note) in enumerate(ch):
        y = 44 + i * 44
        col = EDGE_STROKE if d.startswith("ирмэг") else (CLOUD_STROKE if d.startswith("үүл") else WARN)
        f.rect(cx, y, 150, 30, "#FFFFFF", col, rx=6)
        f.text(cx + 75, y + 20, name, 12.5, INK, mono=True)
        f.text(cx + 162, y + 14, d, 11, col, "start")
        f.text(cx + 162, y + 28, note, 10.5, MUTED, "start")
        f.path(f"M {dev_x} {dev_y} L {dev_x} {dev_y + 12} L 440 {dev_y + 12} L 440 {y + 15} L {cx} {y + 15}",
               color=GRID, arrow=False, sw=1.2)
    f.text(40, 350, "Жишээ сэдэв:", 12, INK, "start", "bold")
    f.text(40, 372, "cnc302/shutis/mhts/lab/pi3b-01/telemetry", 13, CLOUD_STROKE, "start", mono=True)
    f.text(40, 398, "Гүүр зөвхөн cnc302/<SITE>/#-г дамжуулна — угтвар зөрвөл мессеж үүлэнд хүрэхгүй.", 11.5, WARN, "start")
    f.text(40, 420, "Шатлал нь ISA-95-аас санаа авсан курсын тохиролцоо; uns_tree.py --strict шалгана.", 11, MUTED, "start")
    return f


# ═══════════════════════════════════════════════════════════════════════════
#  6. Ачааллын туршилтын бүтэц
# ═══════════════════════════════════════════════════════════════════════════
def fig_loadtest() -> Fig:
    f = new(900, 440, "Ачааллын туршилт")
    f.group(20, 40, 400, 360, "Зөөврийн компьютер", CLOUD_FILL, CLOUD_STROKE)
    f.box(40, 75, 170, 70, "emqtt-bench", ("loadtest.sh", "conn · sub · pub · ramp"))
    f.box(230, 75, 170, 70, "EMQX 5.8", ("--target cloud", "50 → 2000 холболт"), stroke=CLOUD_STROKE)
    f.box(40, 200, 170, 70, "collect_metrics.py", ("--target edge|cloud",))
    f.box(230, 200, 170, 70, "EMQX REST API", ("API key / Bearer", "/api/v5/…?aggregate"))
    f.box(40, 315, 170, 65, "CSV", ("lab04/measurements/",), dash="4 3")
    f.box(230, 315, 170, 65, "plot_scaling.py", ("ирмэг ба үүл", "нэг тэнхлэг дээр"))
    f.group(500, 40, 380, 360, "Raspberry Pi 3B", EDGE_FILL, EDGE_STROKE)
    f.box(530, 75, 320, 70, "Mosquitto (контейнер)", ("--target edge · 10 → 500 холболт",
                                                     "хязгаар: memory 128m"), stroke=EDGE_STROKE)
    f.box(530, 200, 150, 70, "$SYS", ("clients/connected", "store/messages/count"))
    f.box(700, 200, 150, 70, "/proc", ("RAM · swap si/so", "net tx/rx"))
    f.box(530, 315, 320, 65, "Аль нөөц ТҮРҮҮЛЖ ханав?", ("RAM (OOMKilled) · CPU · 100 Mb/s · microSD",),
          fill=WARN_FILL, stroke=WARN)
    f.arrow(210, 110, 230, 110)
    f.path("M 125 145 L 125 170 L 690 170 L 690 145", color=EDGE_STROKE, sw=2.2)
    f.text(460, 188, "ачаалал · LAN", 11, EDGE_STROKE, weight="bold")
    f.arrow(210, 235, 230, 235, both=True)
    f.path("M 170 270 L 170 292 L 480 292 L 480 235 L 530 235", color=MUTED, dash="4 3")
    f.path("M 480 292 L 775 292 L 775 270", color=MUTED, dash="4 3")
    f.text(325, 308, "хэмжүүр", 10.5, MUTED)
    f.arrow(100, 270, 100, 315)
    f.arrow(210, 347, 230, 347)
    f.text(450, 428, "Swap идэвхжвэл (vmstat si/so > 0) хязгаарт аль хэдийн хүрсэн — цааш шахвал Pi царцана.",
           11.5, WARN)
    return f

# ═══════════════════════════════════════════════════════════════════════════
#  7. Өгөгдлийн шугам
# ═══════════════════════════════════════════════════════════════════════════
def fig_pipeline() -> Fig:
    f = new(900, 400, "Өгөгдлийн шугам")
    f.box(20, 70, 125, 70, "EMQX", ("cnc302/+/+/+/+/", "telemetry"), stroke=CLOUD_STROKE,
          fill=CLOUD_FILL, mono_sub=True)
    f.group(165, 30, 530, 235, "Node-RED 4.0 (зөөврийн компьютер)", "#FBFBFD", MUTED, 13)
    f.box(180, 70, 95, 70, "mqtt in", ("QoS 1",))
    f.box(290, 70, 145, 70, "задлан шинжлэх", ("JSON · UNS · муж", "3 гаралт"), tsize=12)
    f.box(450, 60, 110, 44, "line protocol", (), tsize=11.5)
    f.box(450, 112, 110, 44, "integrity", ("seq, rx_ms",), tsize=11.5)
    f.box(575, 70, 105, 70, "http request", ("POST", "write_lp"), tsize=12)
    f.box(575, 175, 105, 70, "шалгах", ("2xx биш →",))
    f.box(290, 175, 145, 70, "dead-letter", ("/data/", "deadletter.jsonl"), fill=BAD_FILL,
          stroke=BAD, mono_sub=True)
    f.box(720, 60, 160, 90, "InfluxDB 3 Core", ("/api/v3/write_lp", "?db=cnc302", "&precision=millisecond"),
          stroke=CLOUD_STROKE, fill=CLOUD_FILL, mono_sub=True)
    f.box(720, 190, 160, 70, "Grafana", ("SQL · $__dateBin(time)", "Flight SQL"), stroke=CLOUD_STROKE,
          fill=CLOUD_FILL)
    f.arrow(145, 105, 180, 105)
    f.arrow(275, 105, 290, 105)
    f.arrow(435, 92, 450, 82)
    f.arrow(435, 118, 450, 132)
    f.arrow(560, 82, 575, 95)
    f.arrow(560, 132, 575, 118)
    f.arrow(680, 105, 720, 105)
    f.arrow(627, 140, 627, 175)
    f.arrow(575, 210, 435, 210, "бичилт унасан", color=BAD, lcolor=BAD)
    f.arrow(362, 140, 362, 175, color=BAD)
    f.text(354, 163, "буруу JSON / сэдэв", 10.5, BAD, "end")
    f.arrow(800, 150, 800, 190)
    f.text(20, 305, "Тэмдэглэл", 12.5, INK, "start", "bold")
    f.lines(20, 327, [
        "• Dead-letter мөр бүр алдааны шалтгаан ба line protocol текстийг (lp) хадгална → дараа нь дахин бичиж болно.",
        "• InfluxDB 3: database анх бичихэд өөрөө үүснэ (schema-on-write); precision=millisecond (v3-ын утга).",
        "• http request: senderr=false — холбогдож чадахгүй үед ч мессеж шалгах зангилаа руу орж dead-letter-т бичигдэнэ.",
    ], 11.5, INK, "start")
    return f

# ═══════════════════════════════════════════════════════════════════════════
#  8. Store-and-forward
# ═══════════════════════════════════════════════════════════════════════════
def fig_bridge_saf() -> Fig:
    f = new(900, 440, "Store-and-forward")
    # plot area
    X0, X1, Y0, Y1 = 90, 860, 60, 270
    f.rect(X0, Y0, X1 - X0, Y1 - Y0, "#FFFFFF", GRID, rx=0, sw=1)
    f.text(X0 - 12, Y0 + 6, "дараалал", 11, MUTED, "end")
    f.text(X0 - 12, Y0 + 20, "(мессеж)", 11, MUTED, "end")
    f.text(X1, Y1 + 20, "хугацаа →", 11, MUTED, "end")
    # phases
    t_cut, t_det, t_up, t_drain = 250, 320, 620, 660
    f.rect(t_cut, Y0, t_up - t_cut, Y1 - Y0, "#FDF3F3", "none", rx=0, sw=0)
    f.text((t_cut + t_up) / 2, Y0 + 18, "өгсөх урсгал (uplink) тасарсан", 12, BAD, weight="bold")
    f.text((X0 + t_cut) / 2, Y0 + 18, "хэвийн", 12, OK, weight="bold")
    f.text((t_up + X1) / 2, Y0 + 18, "сэргэсэн", 12, OK, weight="bold")
    # queue curve: 0 until detect, linear up, then drain
    top = 95
    pts = f"{X0},{Y1-2} {t_det},{Y1-2} {t_up},{top} {t_drain},{Y1-2} {X1},{Y1-2}"
    f.raw(f'<polyline points="{pts}" fill="none" stroke="{EDGE_STROKE}" stroke-width="2.6"/>')
    f.raw(f'<polygon points="{t_det},{Y1-2} {t_up},{top} {t_drain},{Y1-2}" fill="{EDGE_STROKE}" opacity="0.10"/>')
    # markers
    for x, lab, col in [(t_cut, "таслав", BAD), (t_det, "гүүр анзаарав", WARN), (t_up, "сэргэв", OK)]:
        f.raw(f'<line x1="{x}" y1="{Y0}" x2="{x}" y2="{Y1}" stroke="{col}" stroke-width="1.4" stroke-dasharray="5 4"/>')
        f.text(x, Y1 + 20, lab, 11, col)
    f.arrow(t_cut + 4, 238, t_det - 4, 238, both=True, color=WARN)
    f.text((t_cut + t_det) / 2, 232, "≤ keepalive", 10.5, WARN)
    f.text((t_cut + t_det) / 2 + 2, 256, "(15 с)", 10.5, WARN)
    f.text(t_up + 70, 118, "дахин илгээх", 11, EDGE_STROKE, "start", weight="bold")
    f.text(t_up + 70, 132, "(replay burst)", 11, EDGE_STROKE, "start")
    # autosave ticks
    for i, x in enumerate(range(X0 + 60, X1, 120)):
        f.raw(f'<line x1="{x}" y1="{Y1}" x2="{x}" y2="{Y1 + 6}" stroke="{MUTED}" stroke-width="1.2"/>')
    f.text(X0, Y1 + 38, "▲ autosave_interval 60 с: RAM дахь дараалал microSD руу хуулагдана", 10.5, MUTED, "start")

    # notes
    f.text(30, 340, "Юу хэмжих вэ", 12.5, INK, "start", "bold")
    f.lines(30, 362, [
        "• RPO — алдагдсан мессежийн тоо (InfluxDB-ийн integrity хүснэгтэд seq-ийн цоорхой). Терминалаар биш!",
        "• MTTR — сэргэснээс шугам бүрэн болох хүртэлх хугацаа.",
        "• SIGKILL / тэжээл тасрах нь autosave-ээс өмнө болбол RAM дахь дараалал алдагдана; дараалал дүүрвэл ШИНЭ мессеж хаягдана.",
    ], 11.5, INK, "start")
    return f


# ═══════════════════════════════════════════════════════════════════════════
#  9. Ирмэгийн шүүлт
# ═══════════════════════════════════════════════════════════════════════════
def fig_edge_ai() -> Fig:
    f = new(900, 420, "Ирмэгийн шүүлт")
    for i, (title, filt) in enumerate([("А. Шүүлтгүй — бүгдийг үүл рүү", False),
                                       ("Б. Ирмэг дээр шүүх — edge_agent.py --filter --detector", True)]):
        y = 30 + i * 190
        f.text(20, y + 4, title, 13, INK, "start", "bold")
        f.box(20, y + 20, 130, 70, "Мэдрэгч", ("2 с тутам",))
        f.group(180, y + 16, 330, 150, "Raspberry Pi 3B", EDGE_FILL, EDGE_STROKE, 12)
        if filt:
            f.box(200, y + 45, 130, 70, "LiteRT int8", ("[temp, vib, rpm]", "→ score 0..1"),
                  stroke=EDGE_STROKE)
            f.box(350, y + 45, 140, 70, "шүүлт", ("score ≥ 0.6 → илгээ", "+ 15 мөчлөг тутам", "хураангуй"),
                  fill=WARN_FILL, stroke=WARN)
            f.arrow(330, y + 80, 350, y + 80)
        else:
            f.box(200, y + 45, 290, 70, "edge_agent.py", ("мөчлөг бүрт telemetry нийтэлнэ",),
                  stroke=EDGE_STROKE)
        f.arrow(150, y + 55, 200, y + 75)
        # uplink bar
        f.text(540, y + 42, "өгсөх урсгал (uplink) · 100 Mb/s", 11, MUTED, "start")
        f.rect(540, y + 50, 300, 26, "#FFFFFF", GRID, rx=4, sw=1)
        frac = 0.12 if filt else 0.85
        f.rect(540, y + 50, 300 * frac, 26, EDGE_STROKE if filt else BAD,
               "none", rx=4, sw=0)
        f.text(540, y + 96, "мессежийн тоо, байт → Хүснэгт 6.x-д хэмжинэ" if filt
               else "N төхөөрөмж × 0.5 мессеж/с × хэмжээ", 11, MUTED, "start")
        f.arrow(510, y + 63, 540, y + 63, color=EDGE_STROKE if filt else BAD, sw=2.2)
        f.box(855 - 10, y + 40, 50, 46, "☁", (), tsize=16, stroke=CLOUD_STROKE, fill=CLOUD_FILL)
    f.text(450, 408, "Зурвасын урт нь схем — бодит харьцааг /sys/class/net/eth0/statistics/tx_bytes-ээр хэмжинэ.",
           11, MUTED)
    return f


# ═══════════════════════════════════════════════════════════════════════════
#  10. OIDC ба RBAC
# ═══════════════════════════════════════════════════════════════════════════
def fig_oidc_rbac() -> Fig:
    f = new(900, 490, "OIDC ба RBAC")
    cols = [("Клиент", 90, NEUTRAL_STROKE, NEUTRAL_FILL),
            ("Dex (OIDC)", 300, CLOUD_STROKE, CLOUD_FILL),
            ("GraphQL API", 540, CLOUD_STROKE, CLOUD_FILL),
            ("registry / InfluxDB", 790, CLOUD_STROKE, CLOUD_FILL)]
    for name, x, s, fl in cols:
        f.box(x - 80, 20, 160, 38, name, (), fill=fl, stroke=s, tsize=12.5)
        f.raw(f'<line x1="{x}" y1="58" x2="{x}" y2="410" stroke="{GRID}" stroke-width="1.3" stroke-dasharray="4 4"/>')
    y = 92
    for a, b, lab, col in [
        (90, 300, "POST /dex/token  (password grant, Basic client auth)", INK),
        (300, 90, "id_token (JWT · RS256 · kid · iss · aud · exp)", INK),
        (90, 540, "Authorization: Bearer <JWT>", INK),
        (540, 300, "GET jwks_uri (discovery) — нийтийн түлхүүр", MUTED),
    ]:
        f.arrow(a, y, b, y, lab, lsize=11, lcolor=col)
        y += 44
    f.rect(455, y - 16, 170, 104, "#FFFFFF", CLOUD_STROKE, rx=6)
    f.lines(540, y + 2, ["1. гарын үсэг (kid)", "2. alg ∈ {RS256}", "3. iss · aud · exp",
                         "4. үүрэг → эрх"], 11, INK)
    f.text(540, y + 80, "viewer · operator · admin", 10, MUTED)
    f.arrow(625, y + 22, 790, y + 22, "device:read / telemetry:read", lsize=10.5, lcolor=INK)
    f.arrow(790, y + 62, 625, y + 62, "өгөгдөл", lsize=10.5, lcolor=MUTED, loff=16)
    f.arrow(540, y + 120, 90, y + 120, "хариу эсвэл 401 / 403", lsize=11, lcolor=INK)
    f.rect(30, 415, 840, 64, BAD_FILL, BAD, rx=8)
    f.text(46, 437, "Санаатай 2 эмзэг байдал (Лаб 7-д олж засна):", 12, BAD, "start", "bold")
    f.text(46, 456, "① jwt.get_unverified_claims — гарын үсгийг шалгадаггүй", 11.5, BAD, "start")
    f.text(46, 472, "② introspection ба query-гийн нарийвчлал (alias, гүн) хязгааргүй", 11.5, BAD, "start")
    return f

# ═══════════════════════════════════════════════════════════════════════════
#  11. Дижитал ихэр
# ═══════════════════════════════════════════════════════════════════════════
def fig_digital_twin() -> Fig:
    f = new(900, 420, "Дижитал ихэр")
    f.group(20, 60, 190, 300, "Бодит хөрөнгө", EDGE_FILL, EDGE_STROKE, 13)
    f.box(40, 100, 150, 70, "Raspberry Pi 3B", ("edge_agent.py",), stroke=EDGE_STROKE)
    f.box(40, 190, 150, 70, "Mosquitto", ("гүүр → EMQX",), stroke=EDGE_STROKE)
    f.arrow(115, 170, 115, 190)
    f.group(250, 20, 440, 380, "Дижитал ихэр — twin_sync.py", "#FBFBFD", CLOUD_STROKE, 13)
    layers = [
        ("БҮТЭЦ", "build", ["UNS шатлал (site/area/line/device)", "+ registry-ийн төхөөрөмжийн жагсаалт", "→ lab08/out/twin.json"]),
        ("ТӨЛӨВ", "sync", ["InfluxDB-ийн түүх (параметртэй SQL)", "+ MQTT-ээр амьд төлөв (status, bridge/state)", "→ ok · warning · degraded · stale"]),
        ("ЗАН ТӨЛӨВ", "simulate", ["сүүлийн дээжээр хандлага тооцох", "N минутын дараах утгыг таамаглах", "→ --temp-alarm давах уу?"]),
    ]
    for i, (name, cmd, rows) in enumerate(layers):
        y = 55 + i * 112
        f.rect(270, y, 390, 98, "#FFFFFF", CLOUD_STROKE, rx=8)
        f.text(286, y + 24, name, 13, CLOUD_STROKE, "start", "bold")
        f.text(646, y + 24, cmd, 11.5, MUTED, "end", mono=True)
        f.lines(286, y + 46, rows, 11.5, INK, "start")
    f.box(740, 160, 140, 70, "InfluxDB 3", ("telemetry", "twin_state"), stroke=CLOUD_STROKE,
          fill=CLOUD_FILL, mono_sub=True)
    f.box(740, 290, 140, 70, "Ollama + ask.py", ("байгалийн хэл → SQL", "guard_sql()"), stroke=CLOUD_STROKE,
          fill=CLOUD_FILL)
    f.arrow(190, 225, 270, 215)
    f.text(115, 290, "амьд төлөв →", 11, EDGE_STROKE)
    f.arrow(740, 182, 660, 182, "түүх", lsize=11)
    f.arrow(660, 208, 740, 208, "twin_state", lsize=11, loff=16)
    f.arrow(810, 230, 810, 290, dash="4 3")
    f.text(450, 412, "Курсын ажлын тодорхойлолт: бүтэц + төлөв + зан төлөв гурвыг бодит хөрөнгөтэй синхрон байлгасан загвар.",
           11, MUTED)
    return f

# ═══════════════════════════════════════════════════════════════════════════
#  12. K3s кластер
# ═══════════════════════════════════════════════════════════════════════════
def fig_k3s_topology() -> Fig:
    f = new(900, 480, "K3s кластер")
    f.group(20, 30, 420, 400, "Зөөврийн компьютер", CLOUD_FILL, CLOUD_STROKE)
    f.box(40, 70, 120, 250, "Docker Desktop", ("stack/", "", "EMQX :1883", "InfluxDB", "Grafana", "…"),
          stroke=CLOUD_STROKE)
    f.group(175, 70, 250, 250, "VirtualBox VM", VM_FILL, VM_STROKE, 12.5)
    f.text(189, 108, "Ubuntu Server LTS · Bridged", 10.5, MUTED, "start")
    f.text(189, 123, "≥ 2 vCPU · 4 GB (доод тал 2 GB)", 10.5, MUTED, "start")
    f.box(190, 138, 220, 60, "k3s server (amd64)", ("API :6443 · containerd",), stroke=VM_STROKE)
    f.box(190, 210, 105, 50, "coredns", (), tsize=11.5)
    f.box(305, 210, 105, 50, "metrics-server", ("HPA-д",), tsize=11)
    f.text(300, 290, "traefik, servicelb — унтраасан", 10.5, MUTED)
    f.text(268, 362, "kubectl  ·  docker build --platform linux/arm64", 11, INK, mono=True)
    f.text(268, 382, "docker save → edge-agent-v1-arm64.tar → Pi", 11, INK, mono=True)
    f.group(600, 30, 280, 400, "Raspberry Pi 3B", EDGE_FILL, EDGE_STROKE)
    f.box(615, 70, 250, 60, "k3s agent (arm64)", ("≈ 268 MiB (Pi 4B хэмжилт)",), stroke=EDGE_STROKE)
    f.box(615, 145, 120, 90, "mosquitto", ("pod · гүүр", "req 32Mi", "NodePort 31883"), stroke=EDGE_STROKE,
          tsize=12)
    f.box(745, 145, 120, 90, "edge-agent", ("pod · HPA", "req 96Mi", "N = 1…3"),
          stroke=EDGE_STROKE, tsize=12)
    f.rect(615, 250, 250, 60, "#FFFFFF", EDGE_STROKE, rx=6)
    f.text(740, 270, "nodeSelector", 12, INK, weight="bold")
    f.text(740, 287, "kubernetes.io/arch: arm64", 10.5, EDGE_STROKE, mono=True)
    f.text(740, 301, "cnc302/layer: edge", 10.5, EDGE_STROKE, mono=True)
    f.text(740, 336, "Docker, Compose — зогсоосон", 10.5, MUTED)
    f.text(740, 356, "/var/lib/rancher/k3s/agent/images/", 10, INK, mono=True)
    f.text(740, 372, "imagePullPolicy: Never", 10, INK, mono=True)
    f.arrow(615, 100, 410, 160, color=VM_STROKE, sw=2.2)
    f.text(505, 86, "6443/tcp", 11, VM_STROKE, weight="bold", mono=True)
    f.text(505, 101, "agent → server", 10.5, VM_STROKE)
    f.arrow(600, 200, 425, 200, color=MUTED, both=True)
    f.text(512, 193, "8472/udp VXLAN", 10.5, MUTED, mono=True)
    f.arrow(600, 240, 425, 240, color=MUTED, both=True)
    f.text(512, 233, "10250/tcp kubelet", 10.5, MUTED, mono=True)
    f.path("M 615 218 L 607 218 L 607 410 L 100 410 L 100 320", color=EDGE_STROKE, sw=2)
    f.text(330, 402, "MQTT гүүр → EMQX :1883", 11, EDGE_STROKE, weight="bold")
    f.text(450, 462, "Албан ёсны доод шаардлага: server 2 цөм / 2 GB, agent 1 цөм / 512 MB (docs.k3s.io) → server нь Pi дээр биш, VM дээр.",
           11, WARN)
    return f

FIGURES.update({
    "fig-uns-tree": fig_uns_tree,
    "fig-loadtest": fig_loadtest,
    "fig-pipeline": fig_pipeline,
    "fig-bridge-saf": fig_bridge_saf,
    "fig-edge-ai": fig_edge_ai,
    "fig-oidc-rbac": fig_oidc_rbac,
    "fig-digital-twin": fig_digital_twin,
    "fig-k3s-topology": fig_k3s_topology,
})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", action="store_true", help="урьдчилан харах PNG")
    ap.add_argument("--pdf", metavar="DIR", help="LaTeX-д зориулсан PDF бичих хавтас")
    ap.add_argument("only", nargs="*")
    a = ap.parse_args()
    names = a.only or list(FIGURES)
    for n in names:
        svg = FIGURES[n]().svg()
        p = OUT / f"{n}.svg"
        p.write_text(svg, encoding="utf-8")
        msg = f"✓ {p.name}"
        if a.png or a.pdf:
            import cairosvg
            if a.png:
                cairosvg.svg2png(bytestring=svg.encode(), write_to=str(OUT / f"{n}.png"),
                                 output_width=1350)
                msg += " + png"
            if a.pdf:
                d = Path(a.pdf)
                d.mkdir(parents=True, exist_ok=True)
                cairosvg.svg2pdf(bytestring=svg.encode(), write_to=str(d / f"{n}.pdf"))
                msg += " + pdf"
        print(msg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
