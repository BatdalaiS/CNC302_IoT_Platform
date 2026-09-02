#!/usr/bin/env bash
# CNC302 Лаб 4 — Ачааллын тест (emqtt-bench ашиглана)
#
# emqtt-bench бол EMQX-ийн албан ёсны хэмжилтийн хэрэгсэл. Олон мянган
# холболтод Python скриптээс хамаагүй тогтвортой (Erlang дээр бичигдсэн).
#
# ЗӨӨВРИЙН КОМПЬЮТЕР дээр ажиллуулна — Pi-г ачаалахгүйн тулд!
#
# ── ХОЁР ЗОРИЛТ, ХОЁР ӨӨР ХЯЗГААР ────────────────────────────────────────────
#   --target cloud  зөөврийн компьютерийн EMQX. Мянга мянган холболт даана.
#                   Шатууд: 50, 100, 250, 500, 1000, 2000
#   --target edge   Raspberry Pi 3B дээрх mosquitto. ЭНЭ НЬ ЖИЖИГ.
#                   Шатууд: 10, 25, 50, 100, 200, 350, 500   ← анхдагч
#
# ⚠ АНХААР — edge зорилт дээр хязгаар нь ХАМГИЙН МАГАДЛАЛТАЙГААР CPU БИШ:
#     1) САНАХ ОЙ — Pi 3B-д нийт 1 GB (бодитоор ~925 MiB). mosquitto холболт
#        бүрт хэдэн арван KiB буфер эзэлнэ. Сул RAM 150 MiB-ээс доош орвол
#        цөм swap руу орж, microSD дээр бичиж эхэлнэ → бүх тоо гажина.
#     2) 100 Mbit УПЛИНК — Ethernet нь USB 2.0 дээр сууж байгаа тул бодит
#        хурд ~90–95 Mbit бөгөөд USB-тэй зурвасаа хуваана.
#   4×Cortex-A53 нь ихэвчлэн эхлээд дүүрэхгүй. Тиймээс тайланд заавал
#   **АЛЬ НӨӨЦ ТҮРҮҮЛЖ ХАНАСАН БЭ** гэдгийг тоогоор бичих ёстой:
#   RAM (MiB), уплинкийн Mbit, эсвэл CPU %. Хоёр дахь хостын хэмжилтгүйгээр
#   энэ асуултад хариулах боломжгүй.
#
# Хэмжилтийг ЗЭРЭГ ажиллуулна (ирмэгийн хостын дээр):
#   bash tools/measure_stack.sh --role edge --watch 900 5
#   python3 lab04/collect_metrics.py --target edge --label ramp --seconds 900
#
# Ашиглах:
#   bash loadtest.sh conn  pi3b-01.local 100        # 100 идэвхгүй холболт
#   bash loadtest.sh pub   pi3b-01.local 100 1      # 100 нийтлэгч, 1 мсж/с
#   bash loadtest.sh --target edge  ramp pi3b-01.local     # 10→500 шатууд
#   bash loadtest.sh --target cloud ramp 192.168.1.100     # 50→2000 шатууд
#
# ШААРДЛАГА: зөөврийн компьютер дээрх файлын дескрипторын хязгаар
#   Linux/macOS:  ulimit -n 65535
#   Windows:      WSL2 дотор ажиллуулна

set -euo pipefail

IMAGE="${IMAGE:-emqx/emqtt-bench:0.4.20}"
TOPIC="${TOPIC:-cnc302/bench/%i/telemetry}"
PAYLOAD_SIZE="${PAYLOAD_SIZE:-200}"
QOS="${QOS:-1}"
PORT="${PORT:-1883}"
TARGET="edge"
STEP_SECONDS="${STEP_SECONDS:-120}"
REST_SECONDS="${REST_SECONDS:-20}"

# ── Шатны өндөр. edge нь 10→500, cloud нь 50→2000. ──────────────────────────
RAMP_EDGE="10 25 50 100 200 350 500"
RAMP_CLOUD="50 100 250 500 1000 2000"

usage() { sed -n '2,38p' "$0"; }

# ── Тугуудыг эхэнд нь задална, дараа нь хуучин байрлалт аргументууд ─────────
while [ $# -gt 0 ]; do
  case "$1" in
    --target)   TARGET="${2:?--target edge|cloud}"; shift 2 ;;
    --target=*) TARGET="${1#*=}"; shift ;;
    -h|--help)  usage; exit 0 ;;
    *)          break ;;
  esac
done

case "$TARGET" in
  edge|cloud) ;;
  *) echo "--target нь edge эсвэл cloud байх ёстой (өгсөн: $TARGET)" >&2; exit 1 ;;
esac

MODE="${1:?горим: conn|pub|sub|ramp}"
HOST="${2:?брокерийн хаяг}"

LAST_OK=""          # хамгийн сүүлд амжилттай дуусгасан шат

have_docker() { command -v docker >/dev/null 2>&1; }

run_bench() {
  if have_docker; then
    docker run --rm --network host "$IMAGE" "$@"
  else
    emqtt_bench "$@"
  fi
}

# Брокер TCP түвшинд хариулж байна уу? Ханасан брокер шинэ холболт авахаа
# больдог — тэр үед ramp-ыг цаашид үргэлжлүүлэх нь утгагүй.
broker_alive() {
  if timeout 4 bash -c "exec 3<>/dev/tcp/$HOST/$PORT" 2>/dev/null; then
    return 0
  fi
  if command -v nc >/dev/null 2>&1 && nc -z -w 4 "$HOST" "$PORT" 2>/dev/null; then
    return 0
  fi
  return 1
}

report_last_good() {
  echo ""
  echo "════════════════════════════════════════════════════════"
  if [ -n "$LAST_OK" ]; then
    echo " СҮҮЛИЙН АМЖИЛТТАЙ ШАТ : $LAST_OK холболт"
  else
    echo " СҮҮЛИЙН АМЖИЛТТАЙ ШАТ : байхгүй (эхний шат ч давсангүй)"
  fi
  echo " Зорилт                : $TARGET  ($HOST:$PORT)"
  echo ""
  echo " ТАЙЛАНД БИЧИХ ЗҮЙЛ: аль нөөц ТҮРҮҮЛЖ ханасан бэ?"
  if [ "$TARGET" = "edge" ]; then
    echo "   · сул RAM (MiB)      → measure_stack.sh --role edge гаралт"
    echo "   · уплинкийн Mbit     → docker stats-ийн NET I/O өсөлт"
    echo "   · CPU %              → 4×A53 ханасан эсэх"
    echo "   Pi 3B дээр ихэвчлэн RAM эсвэл 100 Mbit уплинк түрүүлдэг, CPU биш."
  else
    echo "   · CPU %, RAM, файлын дескриптор (ulimit -n)"
  fi
  echo "════════════════════════════════════════════════════════"
}

on_interrupt() {
  echo ""
  echo "→ Тасаллаа (Ctrl+C). Шатны түүхийг хэвлэж байна…"
  report_last_good
  exit 130
}
trap on_interrupt INT TERM

case "$MODE" in
  conn)
    N="${3:-100}"
    echo "→ [$TARGET] $N идэвхгүй холболт ($HOST:$PORT). Ctrl+C-ээр зогсооно."
    if [ "$TARGET" = "edge" ] && [ "$N" -gt 500 ]; then
      echo "  ⚠ Pi 3B-гийн mosquitto-д $N холболт хэтэрхий их. RAM дүүрнэ."
    fi
    run_bench conn -h "$HOST" -p "$PORT" -c "$N" -i 10
    ;;

  sub)
    N="${3:-10}"
    echo "→ [$TARGET] $N захиалагч ($HOST:$PORT)"
    run_bench sub -h "$HOST" -p "$PORT" -c "$N" -i 10 -t "$TOPIC" -q "$QOS"
    ;;

  pub)
    N="${3:-100}"; RATE="${4:-1}"
    INTERVAL_MS=$(( 1000 / RATE ))
    echo "→ [$TARGET] $N нийтлэгч × ${RATE} мсж/с = $(( N * RATE )) мсж/с зорилтот"
    if [ "$TARGET" = "edge" ]; then
      echo "  Санамж: $(( N * RATE * PAYLOAD_SIZE * 8 / 1000000 )) Mbit/с орчим"
      echo "  ачаалал уплинк рүү очно (100 Mbit-ийн аль хэсэг вэ?)."
    fi
    run_bench pub -h "$HOST" -p "$PORT" -c "$N" -i 10 -I "$INTERVAL_MS" \
      -t "$TOPIC" -s "$PAYLOAD_SIZE" -q "$QOS"
    ;;

  ramp)
    if [ "$TARGET" = "edge" ]; then RUNGS="$RAMP_EDGE"; else RUNGS="$RAMP_CLOUD"; fi
    echo "════════════════════════════════════════════════════════"
    echo " ШАТ ДАРААЛСАН АЧААЛЛЫН ТЕСТ"
    echo " Зорилт : $TARGET  →  $HOST:$PORT"
    echo " Шатууд : $RUNGS"
    echo " Шат тус бүр ${STEP_SECONDS}с, хооронд ${REST_SECONDS}с амралт"
    echo ""
    if [ "$TARGET" = "edge" ]; then
      echo " ⚠ ИРМЭГИЙН ЗОРИЛТ: хязгаар нь CPU БИШ байх магадлалтай."
      echo "   Pi 3B-д 1 GB RAM, 100 Mbit (USB 2.0) уплинк байна."
      echo "   АЛЬ НӨӨЦ ТҮРҮҮЛЖ ХАНАСАНЫГ заавал бүртгэ — энэ бол үнэлгээний"
      echo "   гол асуулт, зөвхөн 'хэдэн холболт даасан' гэдэг биш."
      echo ""
      echo " Pi ДЭЭР ЗЭРЭГ ажиллуулна:"
      echo "   bash tools/measure_stack.sh --role edge --watch 900 5"
      echo "   python3 lab04/collect_metrics.py --target edge --label ramp --seconds 900"
    else
      echo " Зөөврийн компьютер ДЭЭР ЗЭРЭГ ажиллуулна:"
      echo "   python3 lab04/collect_metrics.py --target cloud --label ramp --seconds 900"
    fi
    echo "════════════════════════════════════════════════════════"
    read -rp "collect_metrics.py ажиллаж эхэлсэн үү? [enter]" _ || true

    if ! broker_alive; then
      echo "✗ $HOST:$PORT хариу өгөхгүй байна. Хаяг/порт болон брокерыг шалгана уу." >&2
      exit 1
    fi

    for N in $RUNGS; do
      echo ""
      echo "──────── ШАТ: $N төхөөрөмж, 1 мсж/с, ${STEP_SECONDS} сек ────────"
      timeout "$STEP_SECONDS" docker run --rm --network host "$IMAGE" pub \
        -h "$HOST" -p "$PORT" -c "$N" -i 10 -I 1000 \
        -t "$TOPIC" -s "$PAYLOAD_SIZE" -q "$QOS" || true

      # Шат дууссаны дараа брокер амьд үлдсэн эсэхийг шалгана.
      if ! broker_alive; then
        echo ""
        echo "✗ БРОКЕР ХАРИУ ӨГӨХӨӨ БОЛИВ ($N холболтын шатны дараа)."
        echo "  Ачааллыг зогсоож, цэвэр гарч байна."
        report_last_good
        exit 2
      fi

      LAST_OK="$N"
      echo "──────── $N дууслаа (брокер амьд). ${REST_SECONDS} сек амарна ────────"
      sleep "$REST_SECONDS"
    done

    echo ""
    echo "→ Бүх шат дууслаа. collect_metrics.py-г зогсоож CSV-г шинжилнэ."
    echo "   python3 lab04/plot_scaling.py measurements/loadtest-ramp-*.csv"
    report_last_good
    ;;

  *)
    usage; exit 1 ;;
esac
