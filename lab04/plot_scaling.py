#!/usr/bin/env python3
"""
CNC302 Лаб 4 — Ачааллын муруй зурах (ирмэг ба үүлийг НЭГ ТЭНХЛЭГ ДЭЭР)

  # нэг муруй
  python3 plot_scaling.py measurements/loadtest-edge-ramp-*.csv

  # ХОЁР МУРУЙ: Raspberry Pi 3B ба зөөврийн компьютер зэрэгцүүлж
  python3 plot_scaling.py measurements/loadtest-edge-*.csv \\
                          measurements/loadtest-cloud-*.csv --out scaling.png

Муруйнуудыг CSV-ийн `target` баганаар (edge | cloud) ялгана. Хуучин, `target`
баганагүй CSV-д файлын нэрээс таана, олдохгүй бол "unknown" гэж үзнэ.

matplotlib байхгүй бол ASCII графикаар зурна (Pi дээр ашигтай) — ASCII
хувилбар дээр ч хоёр муруй нэг талбарт зэрэг гарна: edge = ●, cloud = ○.

Шатны өндөр нь зорилтоос хамаарна:
  edge  (Pi 3B, 1 GB RAM, 100 Mbit): 10, 25, 50, 100, 200, 350, 500
  cloud (зөөврийн компьютер)       : 50, 100, 250, 500, 1000, 2000
"""
from __future__ import annotations
import argparse, csv, os, sys

# loadtest.sh-ийн шатуудтай яг таарна.
RUNGS = {
    "edge":    [10, 25, 50, 100, 200, 350, 500],
    "cloud":   [50, 100, 250, 500, 1000, 2000],
    "unknown": [10, 25, 50, 100, 250, 500, 1000, 2000],
}

MARKERS = {"edge": "●", "cloud": "○", "unknown": "+"}

TARGET_TITLE = {
    "edge": "ирмэг — Raspberry Pi 3B (1 GB, 100 Mbit)",
    "cloud": "үүл — зөөврийн компьютер",
    "unknown": "тодорхойгүй зорилт",
}


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f)]


def num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def row_target(row: dict, path: str) -> str:
    """`target` багана байвал түүнийг, эс бөгөөс файлын нэрээс таана."""
    t = (row.get("target") or "").strip().lower()
    if t in RUNGS:
        return t
    base = os.path.basename(path).lower()
    if "edge" in base:
        return "edge"
    if "cloud" in base:
        return "cloud"
    return "unknown"


# ─────────────────────────── ASCII нөөц график ───────────────────────────

def ascii_plot(series: dict[str, tuple[list[float], list[float]]],
               xlabel: str, ylabel: str, width: int = 60, height: int = 18):
    """
    series: {зорилт: (xs, ys)} — бүх муруйг НЭГ талбарт зэрэг зурна,
    ингэснээр тэнхлэг нь хуваалцсан байна.
    """
    xs_all = [x for xs, _ in series.values() for x in xs]
    ys_all = [y for _, ys in series.values() for y in ys]
    if not xs_all:
        return
    xmin, xmax = min(xs_all), max(xs_all)
    ymin, ymax = min(ys_all), max(ys_all)
    if ymax == ymin:
        ymax = ymin + 1
    grid = [[" "] * width for _ in range(height)]
    for target, (xs, ys) in series.items():
        mark = MARKERS.get(target, "+")
        for x, y in zip(xs, ys):
            cx = int((x - xmin) / max(xmax - xmin, 1e-9) * (width - 1))
            cy = height - 1 - int((y - ymin) / (ymax - ymin) * (height - 1))
            grid[cy][cx] = mark
    legend = "  ".join(f"{MARKERS.get(t, '+')} {t}" for t in series)
    print(f"\n  {ylabel}     [{legend}]")
    print(f"  {ymax:8.1f} ┤" + "".join(grid[0]))
    for row in grid[1:-1]:
        print(f"  {'':8} │" + "".join(row))
    print(f"  {ymin:8.1f} ┤" + "".join(grid[-1]))
    print(f"  {'':8} └" + "─" * width)
    print(f"  {'':9}{xmin:<{width//2}.0f}{xmax:>{width//2}.0f}   {xlabel}")


# ─────────────────────────────── тайлан ───────────────────────────────

def summarise(target: str, rows: list[dict]) -> None:
    conns = [num(r.get("emqx_connections")) for r in rows]
    rate = [num(r.get("emqx_msg_out_rate")) for r in rows]
    cpu = [num(r.get("cpu_total_pct")) for r in rows]
    memfree = [num(r.get("mem_available_mib")) for r in rows]

    print(f"\n  ── {target.upper()}  ({TARGET_TITLE.get(target, target)}) "
          f"— {len(rows)} дээж")
    print(f"     Дээд холболт        : {max(conns):.0f}")
    print(f"     Дээд мессежийн хурд : {max(rate):.1f} мсж/с")
    print(f"     Дээд CPU            : {max(cpu):.1f} %")
    print(f"     Хамгийн бага сул RAM: {min(memfree):.0f} MiB")
    temps = [num(r["temp_c"]) for r in rows if r.get("temp_c")]
    if temps:
        print(f"     Дээд температур     : {max(temps):.1f} °C")
    thr = {r["throttled"] for r in rows if r.get("throttled")}
    if thr - {"0x0"}:
        print(f"     ⚠ THROTTLE илэрлээ  : {thr}  → энэ зорилтын хэмжилт гажсан!")
    if target == "edge" and min(memfree) < 150:
        print(f"     ⚠ Сул RAM 150 MiB-ээс доош оржээ → ХЯЗГААР НЬ САНАХ ОЙ байв."
              f" Тайланд үүнийг бич.")


def bucket_table(target: str, rows: list[dict]) -> None:
    rungs = RUNGS.get(target, RUNGS["unknown"])
    buckets: dict[int, list[dict]] = {}
    for r in rows:
        c = int(num(r.get("emqx_connections")))
        key = min(rungs, key=lambda k: abs(k - c))
        buckets.setdefault(key, []).append(r)

    print(f"\n  {target} — шатлалаар:")
    print(f"  {'холболт':>9} {'дээж':>6} {'мсж/с':>10} {'CPU%':>8} "
          f"{'сул MiB':>9} {'°C':>6}")
    print("  " + "-" * 54)
    for k in sorted(buckets):
        b = buckets[k]
        if len(b) < 2:
            continue
        print(f"  {k:>9} {len(b):>6} "
              f"{sum(num(r.get('emqx_msg_out_rate')) for r in b)/len(b):>10.1f} "
              f"{sum(num(r.get('cpu_total_pct')) for r in b)/len(b):>8.1f} "
              f"{min(num(r.get('mem_available_mib')) for r in b):>9.0f} "
              f"{max((num(r['temp_c']) for r in b if r.get('temp_c')), default=0):>6.1f}")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Ачааллын муруй — ирмэг ба үүлийг нэг тэнхлэг дээр",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("csv", nargs="+",
                   help="нэг буюу хэд хэдэн loadtest-*.csv (edge, cloud холилдож болно)")
    p.add_argument("--out", help="PNG файл (matplotlib шаардана)")
    a = p.parse_args()

    # Бүх файлыг уншаад `target`-аар нь бүлэглэнэ.
    by_target: dict[str, list[dict]] = {}
    for path in a.csv:
        rows = load(path)
        if not rows:
            print(f"  (хоосон CSV алгаслаа: {path})", file=sys.stderr)
            continue
        for r in rows:
            by_target.setdefault(row_target(r, path), []).append(r)

    if not by_target:
        print("Ашиглах өгөгдөл олдсонгүй", file=sys.stderr)
        return 1

    print(f"\n{'═'*66}\n  АЧААЛЛЫН ТЕСТИЙН ДҮН — {len(a.csv)} файл, "
          f"{len(by_target)} зорилт\n{'═'*66}")

    order = [t for t in ("edge", "cloud", "unknown") if t in by_target]
    for t in order:
        summarise(t, by_target[t])
    for t in order:
        bucket_table(t, by_target[t])

    if len(order) > 1:
        print("\n  ХАРЬЦУУЛАЛТ: хоёр муруйг нэг тэнхлэг дээр харьцуулахдаа "
              "'хэдэн\n  холболт даасан' гэдгээс илүү 'АЛЬ НӨӨЦ ТҮРҮҮЛЖ ХАНАСАН' "
              "гэдгийг\n  тайлбарла — ирмэг дээр ихэвчлэн RAM эсвэл 100 Mbit "
              "уплинк, CPU биш.")

    series_rate = {t: ([num(r.get("emqx_connections")) for r in by_target[t]],
                       [num(r.get("emqx_msg_out_rate")) for r in by_target[t]])
                   for t in order}
    series_cpu = {t: ([num(r.get("emqx_connections")) for r in by_target[t]],
                      [num(r.get("cpu_total_pct")) for r in by_target[t]])
                  for t in order}

    if a.out:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            colors = {"edge": "tab:orange", "cloud": "tab:blue",
                      "unknown": "tab:gray"}
            fig, ax = plt.subplots(3, 1, figsize=(9, 11), sharex=True)
            for t in order:
                rows = by_target[t]
                x = [num(r.get("emqx_connections")) for r in rows]
                ax[0].plot(x, [num(r.get("emqx_msg_out_rate")) for r in rows],
                           ".", color=colors.get(t), label=t)
                ax[1].plot(x, [num(r.get("cpu_total_pct")) for r in rows],
                           ".", color=colors.get(t), label=t)
                ax[2].plot(x, [num(r.get("mem_available_mib")) for r in rows],
                           ".", color=colors.get(t), label=t)
            ax[0].set_ylabel("мессеж/сек"); ax[0].grid(alpha=.3); ax[0].legend()
            ax[0].set_title("Ачааллын муруй — ирмэг (Pi 3B) ба үүл (зөөврийн компьютер)")
            ax[1].set_ylabel("CPU %"); ax[1].grid(alpha=.3); ax[1].legend()
            ax[2].set_ylabel("сул RAM (MiB)"); ax[2].grid(alpha=.3); ax[2].legend()
            ax[2].axhline(150, color="tab:red", ls="--", lw=1,
                          label="Pi 3B-гийн аюултай хязгаар 150 MiB")
            ax[2].legend()
            ax[2].set_xlabel("холболтын тоо")
            # Тэнхлэгийн дээд хязгаарыг ӨГӨГДЛӨӨС гаргана (1000 гэж хатуу бичихгүй).
            xmax = max((max(s[0]) for s in series_rate.values() if s[0]), default=1)
            ax[2].set_xlim(0, xmax * 1.05)
            fig.tight_layout(); fig.savefig(a.out, dpi=120)
            print(f"\n  PNG: {a.out}")
        except ImportError:
            print("\n  matplotlib байхгүй — ASCII график:")
            ascii_plot(series_rate, "холболт", "мессеж/сек")
            ascii_plot(series_cpu, "холболт", "CPU %")
    else:
        ascii_plot(series_rate, "холболт", "мессеж/сек")
        ascii_plot(series_cpu, "холболт", "CPU %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
