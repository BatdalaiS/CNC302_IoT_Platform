#!/usr/bin/env bash
# CNC302 Лаб 4 — Ачааллын тест (emqtt-bench ашиглана)
#
# emqtt-bench — EMQX багийн нээлттэй эхийн MQTT хэмжилтийн хэрэгсэл (Erlang).
#   https://github.com/emqx/emqtt-bench  (README: conn/sub/pub дэд команд, туг)
#   Docker дүрс: emqx/emqtt-bench:0.6.3 (amd64 + arm64). Docker байхгүй бол
#   releases хуудаснаас OS-д тохирох бэлэн багцыг татаж, bin/-ийг PATH-д нэмнэ.
#   Сэдэв дэх %i нь клиент бүрийн дэс дугаар (1, 2, 3 …) болж орлоно.
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
#     1) САНАХ ОЙ — Pi 3B-д нийт 1 GB (MemTotal-ыг `free -m`-ээр өөрөө хар).
#        Ирмэгийн mosquitto контейнер 128 MiB хязгаартай (edge/docker-compose.yml):
#        эхлээд ЭНЭ хязгаар ханаж болно (docker stats MEM %, OOMKilled).
#        Хостын сул RAM 150 MiB-ээс доош орвол swap идэвхжиж бүх тоо гажина.
#     2) 100 Mb/s Ethernet өгсөх урсгал (uplink) — албан ёсны үзүүлэлт нь
#        "100 Mb/s Ethernet, 4 × USB 2.0". Ethernet USB-тэй зурвас хуваадаг
#        эсэх нь ТААМАГ — өөрсдөө хэмжиж шалгана.
#   4×Cortex-A53 эхлээд дүүрэх эсэх нь бас таамаг. Тайланд заавал
#   **АЛЬ НӨӨЦ ТҮРҮҮЛЖ ХАНАСАН БЭ** гэдгийг тоогоор бичнэ: RAM (MiB),
#   өгсөх урсгалын Mbit/с, эсвэл CPU %. Хоёр хостын хэмжилтгүйгээр энэ
#   асуултад хариулах боломжгүй.
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
#   Docker-оор ажиллуулахад контейнерт --ulimit nofile-ийг тусад нь өгнө
#   (хостын `ulimit -n` контейнерт шилждэггүй) — доорх run_bench үүнийг хийнэ.

set -euo pipefail

IMAGE="${IMAGE:-emqx/emqtt-bench:0.6.3}"
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

usage() { sed -n '2,45p' "$0"; }

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

# Docker демон ажиллаж байвал дүрсээр, эс бөгөөс PATH дахь emqtt_bench-ээр.
# USE_DOCKER=0 гэж өгвөл заавал бэлэн binary ашиглана.
have_docker() {
  [ "${USE_DOCKER:-auto}" != "0" ] && command -v docker >/dev/null 2>&1 \
    && docker info >/dev/null 2>&1
}

BENCH_NAME="cnc302-bench-$$"

run_bench() {
  if have_docker; then
    docker run --rm --name "$BENCH_NAME" --network host \
      --ulimit nofile=65535:65535 "$IMAGE" "$@"
  else
    emqtt_bench "$@"
  fi
}

# Шатыг хугацаатай ажиллуулна. Docker CLI-г timeout зогсоосны дараа
# контейнер үлдсэн байвал заавал устгана.
run_bench_for() {
  local secs="$1"; shift
  if have_docker; then
    timeout "$secs" docker run --rm --name "$BENCH_NAME" --network host \
      --ulimit nofile=65535:65535 "$IMAGE" "$@" || true
    docker rm -f "$BENCH_NAME" >/dev/null 2>&1 || true
  else
    timeout "$secs" emqtt_bench "$@" || true
  fi
}

# Нэг мессежийн утсан дээрх хэмжээг (байт) тооцоолно:
#   MQTT 5.0 PUBLISH = 1 + RL(1–2) + 2 + сэдэв + 2 (QoS>0) + 1 (property len) + ачаалал
#   TCP сегмент бүрт: TCP 20 + timestamps 12 + IPv4 20 + Ethernet толгой/FCS 18
#   + преамбул/IFG 20 = 90 Б (MSS 1448 гэж үзэв). Олон мессеж нэг сегментэд
#   нийлбэл бодит нэмэгдэл үүнээс бага — энэ нь ДЭЭД үнэлгээ.
wire_bytes() {
  local tlen="$1" size="$2" qos="$3"
  local rem=$(( 2 + tlen + (qos > 0 ? 2 : 0) + 1 + size ))
  local rl=1; [ "$rem" -ge 128 ] && rl=2; [ "$rem" -ge 16384 ] && rl=3
  local mqtt=$(( 1 + rl + rem ))
  local segs=$(( (mqtt + 1447) / 1448 ))
  echo $(( mqtt + segs * 90 ))
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
    echo "   · mosquitto MEM %    → docker stats (128 MiB хязгаарын хэдэн %)"
    echo "   · өгсөх урсгал Mbit/с → Pi-гийн eth0 tx_bytes өсөлт"
    echo "   · CPU %              → 4×A53 ханасан эсэх"
    echo "   Таамгаа (Хүснэгт 4.2) хэмжилттэй харьцуул."
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
    TLEN=$(( ${#TOPIC} - 2 + ${#N} ))          # %i → хамгийн урт дугаар
    WB=$(wire_bytes "$TLEN" "$PAYLOAD_SIZE" "$QOS")
    awk -v n="$N" -v r="$RATE" -v s="$PAYLOAD_SIZE" -v w="$WB" 'BEGIN {
      printf "  Зөвхөн ачаалал : %.2f Mbit/с  (%d Б × 8)\n", n*r*s*8/1e6, s
      printf "  Утсан дээр ≈    : %.2f Mbit/с  (%d Б/мсж: MQTT+TCP/IP+Ethernet)\n", n*r*w*8/1e6, w }'
    if [ "$TARGET" = "edge" ]; then
      echo "  Сэдэв гүүрийн 'out' дүрэмд багтвал ижил хэмжээ Pi-гаас өгсөх урсгал"
      echo "  (uplink)-аар үүл рүү дахин гарна (100 Mb/s-ийн аль хэсэг вэ?)."
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
      echo "   Pi 3B: 1 GB RAM, 100 Mb/s Ethernet; mosquitto контейнер 128 MiB хязгаартай."
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
      run_bench_for "$STEP_SECONDS" pub \
        -h "$HOST" -p "$PORT" -c "$N" -i 10 -I 1000 \
        -t "$TOPIC" -s "$PAYLOAD_SIZE" -q "$QOS"

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
    echo "   python3 lab04/plot_scaling.py measurements/loadtest-${TARGET}-ramp-*.csv"
    report_last_good
    ;;

  *)
    usage; exit 1 ;;
esac
