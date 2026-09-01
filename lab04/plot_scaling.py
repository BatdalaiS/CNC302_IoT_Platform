#!/usr/bin/env python3
"""
CNC302 Лаб 4 — Ачааллын муруй зурах

  python3 plot_scaling.py measurements/loadtest-ramp-*.csv
  python3 plot_scaling.py measurements/loadtest-ramp-*.csv --out scaling.png

matplotlib байхгүй бол ASCII графикаар зурна (Pi дээр ашигтай).
"""
from __future__ import annotations
import argparse, csv, sys


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f)]


def num(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def ascii_plot(xs, ys, xlabel, ylabel, width=60, height=18):
    if not xs:
        return
    xmin, xmax = min(xs), max(xs)
    ymin, ymax = min(ys), max(ys)
    if ymax == ymin:
        ymax = ymin + 1
    grid = [[" "] * width for _ in range(height)]
    for x, y in zip(xs, ys):
        cx = int((x - xmin) / max(xmax - xmin, 1e-9) * (width - 1))
        cy = height - 1 - int((y - ymin) / (ymax - ymin) * (height - 1))
        grid[cy][cx] = "●"
    print(f"\n  {ylabel}")
    print(f"  {ymax:8.1f} ┤" + "".join(grid[0]))
    for row in grid[1:-1]:
        print(f"  {'':8} │" + "".join(row))
    print(f"  {ymin:8.1f} ┤" + "".join(grid[-1]))
    print(f"  {'':8} └" + "─" * width)
    print(f"  {'':9}{xmin:<{width//2}.0f}{xmax:>{width//2}.0f}   {xlabel}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("csv")
    p.add_argument("--out", help="PNG файл (matplotlib шаардана)")
    a = p.parse_args()

    rows = load(a.csv)
    if not rows:
        print("CSV хоосон байна", file=sys.stderr); return 1

    conns = [num(r["emqx_connections"]) for r in rows]
    rate = [num(r["emqx_msg_out_rate"]) for r in rows]
    cpu = [num(r["cpu_total_pct"]) for r in rows]
    memfree = [num(r["mem_available_mib"]) for r in rows]

    print(f"\n{'═'*66}\n  АЧААЛЛЫН ТЕСТИЙН ДҮН — {a.csv}\n{'═'*66}")
    print(f"  Дээд холболт        : {max(conns):.0f}")
    print(f"  Дээд мессежийн хурд : {max(rate):.1f} мсж/с")
    print(f"  Дээд CPU            : {max(cpu):.1f} %")
    print(f"  Хамгийн бага сул RAM: {min(memfree):.0f} MiB")
    temps = [num(r["temp_c"]) for r in rows if r["temp_c"]]
    if temps:
        print(f"  Дээд температур     : {max(temps):.1f} °C")
    thr = {r["throttled"] for r in rows if r["throttled"]}
    if thr - {"0x0"}:
        print(f"  ⚠ THROTTLE илэрлээ  : {thr}  → хэмжилт гажсан!")

    # шатлалаар нэгтгэх
    buckets: dict[int, list[dict]] = {}
    for r in rows:
        c = int(num(r["emqx_connections"]))
        key = min([10, 50, 100, 250, 500, 1000, 2000],
                  key=lambda k: abs(k - c))
        buckets.setdefault(key, []).append(r)

    print(f"\n  {'холболт':>9} {'дээж':>6} {'мсж/с':>10} {'CPU%':>8} "
          f"{'сул MiB':>9} {'°C':>6}")
    print("  " + "-" * 54)
    for k in sorted(buckets):
        b = buckets[k]
        if len(b) < 2:
            continue
        print(f"  {k:>9} {len(b):>6} "
              f"{sum(num(r['emqx_msg_out_rate']) for r in b)/len(b):>10.1f} "
              f"{sum(num(r['cpu_total_pct']) for r in b)/len(b):>8.1f} "
              f"{min(num(r['mem_available_mib']) for r in b):>9.0f} "
              f"{max((num(r['temp_c']) for r in b if r['temp_c']), default=0):>6.1f}")

    if a.out:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(2, 1, figsize=(9, 8), sharex=True)
            ax[0].plot(conns, rate, ".-")
            ax[0].set_ylabel("мессеж/сек"); ax[0].grid(alpha=.3)
            ax[0].set_title("Ачааллын муруй — Raspberry Pi 5")
            ax[1].plot(conns, cpu, ".-", color="tab:red", label="CPU %")
            ax[1].set_ylabel("CPU %"); ax[1].set_xlabel("холболтын тоо")
            ax[1].grid(alpha=.3)
            ax2 = ax[1].twinx()
            ax2.plot(conns, memfree, ".-", color="tab:blue", label="сул RAM MiB")
            ax2.set_ylabel("сул RAM (MiB)")
            fig.tight_layout(); fig.savefig(a.out, dpi=120)
            print(f"\n  PNG: {a.out}")
        except ImportError:
            print("\n  matplotlib байхгүй — ASCII график:")
            ascii_plot(conns, rate, "холболт", "мессеж/сек")
            ascii_plot(conns, cpu, "холболт", "CPU %")
    else:
        ascii_plot(conns, rate, "холболт", "мессеж/сек")
        ascii_plot(conns, cpu, "холболт", "CPU %")
    return 0


if __name__ == "__main__":
    sys.exit(main())
