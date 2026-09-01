#!/usr/bin/env bash
# CNC302 Лаб 4 — Ачааллын тест (emqtt-bench ашиглана)
#
# emqtt-bench бол EMQX-ийн албан ёсны хэмжилтийн хэрэгсэл. 1000+ холболтод
# Python скриптээс хамаагүй тогтвортой (Erlang дээр бичигдсэн).
#
# ЗӨӨВРИЙН КОМПЬЮТЕР дээр ажиллуулна (Pi-г ачаалахгүйн тулд!).
#
#   bash loadtest.sh conn  pi-team03.local 100      # 100 идэвхгүй холболт
#   bash loadtest.sh pub   pi-team03.local 100 1    # 100 нийтлэгч, 1 мсж/с
#   bash loadtest.sh ramp  pi-team03.local          # 10→100→500→1000 шат дараалан
#
# ШААРДЛАГА: зөөврийн компьютер дээрх файлын дескрипторын хязгаар
#   Linux/macOS:  ulimit -n 65535
#   Windows:      WSL2 дотор ажиллуулна

set -euo pipefail

IMAGE="${IMAGE:-emqx/emqtt-bench:0.4.20}"
MODE="${1:?горим: conn|pub|sub|ramp}"
HOST="${2:?брокерийн хаяг}"
TOPIC="${TOPIC:-cnc302/bench/%i/telemetry}"
PAYLOAD_SIZE="${PAYLOAD_SIZE:-200}"
QOS="${QOS:-1}"

have_docker() { command -v docker >/dev/null 2>&1; }

run_bench() {
  if have_docker; then
    docker run --rm --network host "$IMAGE" "$@"
  else
    emqtt_bench "$@"
  fi
}

case "$MODE" in
  conn)
    N="${3:-100}"
    echo "→ $N идэвхгүй холболт ($HOST). Ctrl+C-ээр зогсооно."
    run_bench conn -h "$HOST" -p 1883 -c "$N" -i 10
    ;;
  sub)
    N="${3:-10}"
    echo "→ $N захиалагч"
    run_bench sub -h "$HOST" -p 1883 -c "$N" -i 10 -t "$TOPIC" -q "$QOS"
    ;;
  pub)
    N="${3:-100}"; RATE="${4:-1}"
    INTERVAL_MS=$(( 1000 / RATE ))
    echo "→ $N нийтлэгч × ${RATE} мсж/с = $(( N * RATE )) мсж/с зорилтот"
    run_bench pub -h "$HOST" -p 1883 -c "$N" -i 10 -I "$INTERVAL_MS" \
      -t "$TOPIC" -s "$PAYLOAD_SIZE" -q "$QOS"
    ;;
  ramp)
    echo "════════════════════════════════════════════════════════"
    echo " ШАТ ДАРААЛСАН АЧААЛЛЫН ТЕСТ"
    echo " Pi дээр ЗЭРЭГ ажиллуулна:"
    echo "   python3 lab04/collect_metrics.py --label ramp --seconds 900"
    echo "════════════════════════════════════════════════════════"
    read -rp "collect_metrics.py ажиллаж эхэлсэн үү? [enter]"
    for N in 10 50 100 250 500 1000; do
      echo ""
      echo "──────── ШАТ: $N төхөөрөмж, 1 мсж/с, 120 сек ────────"
      timeout 120 docker run --rm --network host "$IMAGE" pub \
        -h "$HOST" -p 1883 -c "$N" -i 10 -I 1000 \
        -t "$TOPIC" -s "$PAYLOAD_SIZE" -q "$QOS" || true
      echo "──────── $N дууслаа. 20 сек амарна ────────"
      sleep 20
    done
    echo ""
    echo "→ Бүх шат дууслаа. collect_metrics.py-г зогсоож CSV-г шинжилнэ."
    ;;
  *)
    sed -n '2,18p' "$0"; exit 1 ;;
esac
