#!/usr/bin/env bash
# CNC302 — стекийн нөөцийн хэрэглээг хэмжиж CSV болгон бичнэ (Лаб 1, Лаб 4)
#
# Хичээлийн стек ХОЁР хостод хуваагдсан тул энэ скрипт ХОЁР үүрэгтэй:
#
#   --role edge    Raspberry Pi 3B — 1 GB RAM, 4×Cortex-A53 @1.2 GHz,
#                  100 Mb/s Ethernet, 4×USB 2.0, microSD (албан ёсны үзүүлэлт).
#                  Ажиллах зүйл: mosquitto (гүүр) + ирмэгийн агент.
#   --role cloud   Зөөврийн компьютер — cnc302-cloud төсөл:
#                  emqx, influxdb, grafana, registry, nodered …
#
# Үүргийг заагаагүй бол АВТОМАТААР тодорхойлно: /proc/device-tree/model дотор
# "Raspberry Pi" гэж байвал edge, үгүй бол cloud.
#
# Ашиглах:
#   bash tools/measure_stack.sh                        # автомат, нэг агшин
#   bash tools/measure_stack.sh --role edge            # Pi дээр
#   bash tools/measure_stack.sh --role cloud --watch 60 5
#   bash tools/measure_stack.sh --startup              # эхлэх хугацааг хэмжинэ
#
# ⚠ ЧУХАЛ: Pi 3B дээр throttle (get_throttled != 0x0) илэрсэн бол, эсвэл сул
#   санах ой 150 MiB-ээс бага болсон бол ЭНЭ ХЭМЖИЛТ ХҮЧИНГҮЙ. Хичээлийн бүх
#   саатлын тоо тэр үед гажина. Скрипт үүнийг чангаар анхааруулна.
#
# Гаралт: measurements/stack-YYYYmmdd-HHMMSS.csv

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

OUTDIR="${OUTDIR:-measurements}"
mkdir -p "$OUTDIR"
TS=$(date +%Y%m%d-%H%M%S)

RAM_WARN_MIB="${RAM_WARN_MIB:-150}"     # энэ доогуур бол чанга анхааруулга

ROLE=""
MODE="single"
WATCH_DUR=60
WATCH_STEP=5

hr() { printf '%.0s─' {1..72}; echo; }

usage() { sed -n '2,25p' "$0"; }

# ─────────────────────────── үүрэг тодорхойлох ───────────────────────────

MODEL_FILE="/proc/device-tree/model"

detect_role() {
  if [ -r "$MODEL_FILE" ] && tr -d '\0' < "$MODEL_FILE" | grep -qi 'raspberry pi'; then
    echo "edge"
  else
    echo "cloud"
  fi
}

pi_model() {
  if [ -r "$MODEL_FILE" ]; then
    tr -d '\0' < "$MODEL_FILE"
  else
    echo "тодорхойгүй (Pi биш)"
  fi
}

# ─────────────────────── throttle-ийн энгийн тайлбар ───────────────────────
# vcgencmd get_throttled нь битийн маск буцаана. 0x0 = бүх зүйл хэвийн.
explain_throttled() {
  local raw="${1:-}"
  local hex="${raw#*=}"
  if [ -z "$hex" ] || [ "$hex" = "n/a" ]; then
    echo "  (vcgencmd байхгүй — Pi биш эсвэл эрх дутуу)"
    return 0
  fi
  if [ "$hex" = "0x0" ]; then
    echo "  ✓ Хэвийн: тэжээл ба температур хязгаарт хүрээгүй."
    return 0
  fi

  local v=$(( hex ))
  echo "  ⚠ THROTTLE ИЛЭРСЭН ($hex). Утга нь:"
  bit()  { if [ $(( v & $1 )) -ne 0 ]; then echo "     · $2"; fi; }
  bit 0x1     "ОДОО тэжээлийн хүчдэл доогуур байна (адаптер сул)"
  bit 0x2     "ОДОО ARM-ийн давтамж хиймлээр буурсан"
  bit 0x4     "ОДОО throttle хийгдэж байна (процессор удаашрав)"
  bit 0x8     "ОДОО температурын зөөлөн хязгаарт хүрсэн"
  bit 0x10000 "Ачаалснаас хойш хүчдэл доогуур болж БАЙСАН"
  bit 0x20000 "Ачаалснаас хойш давтамж буурч БАЙСАН"
  bit 0x40000 "Ачаалснаас хойш throttle хийгдэж БАЙСАН"
  bit 0x80000 "Ачаалснаас хойш температурын хязгаарт хүрч БАЙСАН"
  echo "     → Шалтгаан нь ихэвчлэн: сул тэжээлийн адаптер эсвэл хөргөлт дутуу."
  echo "     → ЭНЭ ҮЕИЙН БҮХ СААТЛЫН ХЭМЖИЛТ ХҮЧИНГҮЙ. Засаад дахин хэмжинэ үү."
  return 0
}

mem_available_mib() { free -m | awk '/^Mem:/{print $7}'; }
mem_total_mib()     { free -m | awk '/^Mem:/{print $2}'; }
swap_used_mib()     { free -m | awk '/^Swap:/{print $3}'; }

warn_low_ram() {
  local avail="${1:-0}"
  if [ "${avail:-0}" -lt "$RAM_WARN_MIB" ]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════════╗"
    echo "║  ⚠⚠  САНАХ ОЙ ДУУСАХ ДӨХӨЖ БАЙНА: ${avail} MiB сул              "
    echo "║  Хязгаар: ${RAM_WARN_MIB} MiB. Үүнээс доош орвол цөм swap руу     "
    echo "║  шилжиж, microSD дээр бичих болно → саатал 10-100 дахин өснө.     "
    echo "║  ЭНЭ ҮЕД ХЭМЖСЭН БҮХ ТОО ХҮЧИНГҮЙ.                               "
    echo "║  Хийх зүйл: илүү контейнер зогсоо, --devices тоог бууруул.        "
    echo "╚══════════════════════════════════════════════════════════════════╝"
    echo ""
  fi
}

# ──────────────────────────── систем мэдээлэл ────────────────────────────

sysinfo_edge() {
  local thr temp avail
  thr=$(vcgencmd get_throttled 2>/dev/null || echo "throttled=n/a")
  temp=$(vcgencmd measure_temp 2>/dev/null || \
         awk '{printf "temp=%.1f'\''C\n", $1/1000}' /sys/class/thermal/thermal_zone0/temp 2>/dev/null || \
         echo "temp=n/a")
  avail=$(mem_available_mib)

  hr
  echo "ҮҮРЭГ      : edge — Raspberry Pi 3B (ирмэгийн давхарга)"
  echo "Огноо      : $(date -Is)"
  echo "Хост       : $(hostname)"
  echo "Модель     : $(pi_model)"
  echo "Цөм        : $(nproc) ширхэг (Cortex-A53 @1.2 GHz)"
  echo "Санах ой   : $(mem_total_mib) MiB нийт, ${avail} MiB боломжтой"
  echo "             (Pi 3B дээр нийт ~925 MiB байвал хэвийн)"
  echo "Swap       : $(swap_used_mib) MiB ашиглагдсан"
  echo "Ачаалал    : $(cut -d' ' -f1-3 /proc/loadavg)  (1/5/15 мин, 4 цөм)"
  echo "microSD    : $(df -h / | awk 'NR==2{print $2" нийт, "$4" сул, "$5" дүүрсэн"}')"
  echo "Температур : ${temp#*=}" | sed "s/'C/°C/"
  echo "Throttle   : ${thr#*=}"
  explain_throttled "$thr"
  echo "Сүлжээ     : 100 Mb/s Ethernet (албан ёсны үзүүлэлт; бодит хурдыг хэмжинэ)"
  echo "Docker     : $(docker --version 2>/dev/null || echo 'суугаагүй')"
  hr
  warn_low_ram "$avail"
}

sysinfo_cloud() {
  local avail
  avail=$(mem_available_mib)
  hr
  echo "ҮҮРЭГ      : cloud — зөөврийн компьютер (үүлний давхарга)"
  echo "Огноо      : $(date -Is)"
  echo "Хост       : $(hostname)"
  echo "Цөм        : $(nproc) ширхэг"
  echo "Санах ой   : $(mem_total_mib) MiB нийт, ${avail} MiB боломжтой"
  echo "Swap       : $(swap_used_mib) MiB ашиглагдсан"
  echo "Ачаалал    : $(cut -d' ' -f1-3 /proc/loadavg)"
  echo "Диск       : $(df -h / | awk 'NR==2{print $2" нийт, "$4" сул"}')"
  echo "Docker     : $(docker --version 2>/dev/null || echo 'суугаагүй')"
  echo "Төсөл      : cnc302-cloud"
  hr
}

sysinfo() {
  if [ "$ROLE" = "edge" ]; then sysinfo_edge; else sysinfo_cloud; fi
}

# ────────────────────── docker stats тухайн үүргээр ──────────────────────

project_name() {
  [ "$ROLE" = "edge" ] && echo "cnc302-edge" || echo "cnc302-cloud"
}

compose_dir() {
  [ "$ROLE" = "edge" ] && echo "$REPO_DIR/edge" || echo "$REPO_DIR/stack"
}

# Тухайн үүргийн контейнеруудын нэрийг л авна (нөгөө хостынхыг хольж болохгүй).
role_containers() {
  local proj; proj=$(project_name)
  local names
  names=$(docker ps --filter "label=com.docker.compose.project=$proj" \
          --format '{{.Names}}' 2>/dev/null || true)
  if [ -z "$names" ]; then
    # шошго олдоогүй (гараар асаасан) — нэрээр нь барина
    if [ "$ROLE" = "edge" ]; then
      names=$(docker ps --format '{{.Names}}' 2>/dev/null \
              | grep -E '^cnc302-(mosquitto|edge-agent)' || true)
    else
      names=$(docker ps --format '{{.Names}}' 2>/dev/null \
              | grep -E '^cnc302-' | grep -vE '^cnc302-(mosquitto|edge-agent)' || true)
    fi
  fi
  echo "$names"
}

snapshot() {
  local out="$1" tag="$2"
  local names; names=$(role_containers)
  if [ -z "$names" ]; then
    echo "  (ажиллаж буй $(project_name) контейнер алга)" >&2
    return 0
  fi
  # shellcheck disable=SC2086
  docker stats --no-stream --format \
    '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}' \
    $names \
  | while IFS= read -r line; do
      echo "$(date -Is),${ROLE},${tag},${line}"
    done >> "$out"
}

csv_header() {
  echo "timestamp,role,tag,name,cpu_pct,mem_usage,mem_pct,net_io,block_io,pids" > "$1"
}

# ──────────────────────── эхлэх хугацааны хэмжилт ────────────────────────

measure_startup() {
  local out="$OUTDIR/startup-$ROLE-$TS.csv"
  local dir; dir=$(compose_dir)
  # edge дээр профайл хэрэггүй (mosquitto анхдагчаар асна), cloud дээр core.
  local profiles
  if [ "$ROLE" = "cloud" ]; then profiles="--profile core"; else profiles=""; fi

  echo "service,role,created,started,startup_seconds,health" > "$out"
  echo "→ [$ROLE] Стекийг бүрэн зогсоож дахин эхлүүлнэ (өгөгдөл хадгалагдана)…"
  echo "   Compose фолдер: $dir"
  # shellcheck disable=SC2086
  ( cd "$dir" && docker compose $profiles down ) || true
  sync; sleep 3

  local t0; t0=$(date +%s.%N)
  # shellcheck disable=SC2086
  ( cd "$dir" && docker compose $profiles up -d )
  echo "→ Бүх үйлчилгээ healthy болтол хүлээж байна…"

  # Pi 3B microSD дээр EMQX/Influx байхгүй ч mosquitto удаан асахыг хэмжинэ.
  local timeout_s=420
  if [ "$ROLE" = "edge" ]; then timeout_s=180; fi
  local deadline=$(( $(date +%s) + timeout_s ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    local pending
    pending=$(docker ps --filter "label=com.docker.compose.project=$(project_name)" \
              --format '{{.Names}} {{.Status}}' | grep -c "starting" || true)
    [ "$pending" -eq 0 ] && break
    sleep 5
  done
  local t1; t1=$(date +%s.%N)
  echo "→ Нийт бэлэн болох хугацаа: $(echo "$t1 - $t0" | bc) сек"

  local name
  for name in $(role_containers); do
    local created started health secs
    created=$(docker inspect -f '{{.Created}}' "$name")
    started=$(docker inspect -f '{{.State.StartedAt}}' "$name")
    health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name")
    secs=$(( $(date -d "$started" +%s) - $(date -d "$created" +%s) ))
    echo "$name,$ROLE,$created,$started,$secs,$health" >> "$out"
  done
  echo "→ Бичигдлээ: $out"
  column -s, -t "$out" 2>/dev/null || cat "$out"

  if [ "$ROLE" = "edge" ]; then
    echo ""
    echo "  Санамж: Pi 3B-гийн microSD нь ~20–40 MB/s. Дүрс татах, задлах"
    echo "  хугацаа нь зөөврийн компьютерийнхаас 5–10 дахин удаан байх нь хэвийн."
  fi
}

# ────────────────────────────── аргумент задлах ──────────────────────────────

while [ $# -gt 0 ]; do
  case "$1" in
    --role)
      ROLE="${2:?--role edge|cloud}"; shift 2 ;;
    --role=*)
      ROLE="${1#*=}"; shift ;;
    --startup)
      MODE="startup"; shift ;;
    --watch)
      MODE="watch"; WATCH_DUR="${2:-60}"; WATCH_STEP="${3:-5}"; shift
      if [ $# -gt 0 ]; then shift; fi
      if [ $# -gt 0 ]; then shift; fi
      ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Танихгүй аргумент: $1" >&2; usage; exit 1 ;;
  esac
done

if [ -z "$ROLE" ]; then
  ROLE=$(detect_role)
  echo "→ Үүрэг автоматаар тодорхойлогдлоо: $ROLE  (--role-оор дарж болно)" >&2
fi

case "$ROLE" in
  edge|cloud) ;;
  *) echo "--role нь edge эсвэл cloud байх ёстой (өгсөн: $ROLE)" >&2; exit 1 ;;
esac

# ──────────────────────────── үндсэн хэсэг ────────────────────────────

main() {
  sysinfo | tee "$OUTDIR/sysinfo-$ROLE-$TS.txt"

  case "$MODE" in
    startup)
      measure_startup
      ;;
    watch)
      local out="$OUTDIR/stack-$ROLE-$TS.csv"
      csv_header "$out"
      echo "→ [$ROLE] ${WATCH_DUR} сек турш ${WATCH_STEP} сек тутам хэмжинэ…"
      local end=$(( $(date +%s) + WATCH_DUR ))
      while [ "$(date +%s)" -lt "$end" ]; do
        snapshot "$out" "watch"
        if [ "$ROLE" = "edge" ]; then
          warn_low_ram "$(mem_available_mib)"
          local thr; thr=$(vcgencmd get_throttled 2>/dev/null || echo "throttled=0x0")
          [ "${thr#*=}" = "0x0" ] || explain_throttled "$thr"
        fi
        sleep "$WATCH_STEP"
      done
      echo "→ Бичигдлээ: $out"
      awk -F, 'NR>1 {gsub(/%/,"",$5); cpu[$4]+=$5; n[$4]++}
               END {printf "\n%-24s %10s\n","КОНТЕЙНЕР","дундаж CPU%";
                    for (c in cpu) printf "%-24s %10.2f\n", c, cpu[c]/n[c]}' "$out"
      ;;
    *)
      local out="$OUTDIR/stack-$ROLE-$TS.csv"
      csv_header "$out"
      snapshot "$out" "single"
      echo "→ Бичигдлээ: $out"
      column -s, -t "$out" 2>/dev/null || cat "$out"
      ;;
  esac
}

main
