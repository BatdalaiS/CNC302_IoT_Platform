#!/usr/bin/env bash
# CNC302 — стекийн нөөцийн хэрэглээг хэмжиж CSV болгон бичнэ (Лаб 1)
#
# Ашиглах (Raspberry Pi дээр, stack/ фолдероос):
#   bash ../tools/measure_stack.sh                 # нэг агшны хэмжилт
#   bash ../tools/measure_stack.sh --watch 60 5    # 60 сек, 5 сек тутам
#   bash ../tools/measure_stack.sh --startup       # эхлэх хугацааг хэмжинэ
#
# Гаралт: measurements/stack-YYYYmmdd-HHMMSS.csv

set -euo pipefail

OUTDIR="${OUTDIR:-measurements}"
mkdir -p "$OUTDIR"
TS=$(date +%Y%m%d-%H%M%S)

hr() { printf '%.0s─' {1..72}; echo; }

sysinfo() {
  hr
  echo "Огноо      : $(date -Is)"
  echo "Хост       : $(hostname)"
  echo "Модель     : $(tr -d '\0' < /proc/device-tree/model 2>/dev/null || echo 'тодорхойгүй')"
  echo "Цөм        : $(nproc) ширхэг"
  echo "Санах ой   : $(free -h | awk '/^Mem:/{print $2" нийт, "$3" ашиглагдсан, "$7" боломжтой"}')"
  echo "Swap       : $(free -h | awk '/^Swap:/{print $2" нийт, "$3" ашиглагдсан"}')"
  echo "Диск       : $(df -h / | awk 'NR==2{print $2" нийт, "$4" сул"}')"
  echo "Температур : $(vcgencmd measure_temp 2>/dev/null || echo 'n/a')"
  echo "Throttle   : $(vcgencmd get_throttled 2>/dev/null || echo 'n/a')"
  echo "Docker     : $(docker --version)"
  hr
}

snapshot() {
  local out="$1" tag="$2"
  docker stats --no-stream --format \
    '{{.Name}},{{.CPUPerc}},{{.MemUsage}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}},{{.PIDs}}' \
  | while IFS= read -r line; do
      echo "$(date -Is),${tag},${line}"
    done >> "$out"
}

measure_startup() {
  local out="$OUTDIR/startup-$TS.csv"
  echo "service,created,started,startup_seconds,health" > "$out"
  echo "→ Стекийг бүрэн зогсоож дахин эхлүүлнэ (өгөгдөл хадгалагдана)…"
  docker compose --profile core down
  sync; sleep 3

  local t0; t0=$(date +%s.%N)
  docker compose --profile core up -d
  echo "→ Бүх үйлчилгээ healthy болтол хүлээж байна…"

  local deadline=$(( $(date +%s) + 420 ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    local pending
    pending=$(docker ps --filter "name=cnc302-" --format '{{.Names}} {{.Status}}' \
              | grep -c "starting" || true)
    [ "$pending" -eq 0 ] && break
    sleep 5
  done
  local t1; t1=$(date +%s.%N)
  echo "→ Нийт бэлэн болох хугацаа: $(echo "$t1 - $t0" | bc) сек"

  for name in $(docker ps --filter "name=cnc302-" --format '{{.Names}}'); do
    local created started health
    created=$(docker inspect -f '{{.Created}}' "$name")
    started=$(docker inspect -f '{{.State.StartedAt}}' "$name")
    health=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name")
    local secs
    secs=$(( $(date -d "$started" +%s) - $(date -d "$created" +%s) ))
    echo "$name,$created,$started,$secs,$health" >> "$out"
  done
  echo "→ Бичигдлээ: $out"
  column -s, -t "$out"
}

main() {
  sysinfo | tee "$OUTDIR/sysinfo-$TS.txt"

  case "${1:-}" in
    --startup)
      measure_startup
      ;;
    --watch)
      local dur="${2:-60}" step="${3:-5}"
      local out="$OUTDIR/stack-$TS.csv"
      echo "timestamp,tag,name,cpu_pct,mem_usage,mem_pct,net_io,block_io,pids" > "$out"
      echo "→ ${dur} сек турш ${step} сек тутам хэмжинэ…"
      local end=$(( $(date +%s) + dur ))
      while [ "$(date +%s)" -lt "$end" ]; do
        snapshot "$out" "watch"
        sleep "$step"
      done
      echo "→ Бичигдлээ: $out"
      awk -F, 'NR>1 {gsub(/%/,"",$4); cpu[$3]+=$4; n[$3]++}
               END {printf "\n%-24s %10s\n","КОНТЕЙНЕР","дундаж CPU%";
                    for (c in cpu) printf "%-24s %10.2f\n", c, cpu[c]/n[c]}' "$out"
      ;;
    *)
      local out="$OUTDIR/stack-$TS.csv"
      echo "timestamp,tag,name,cpu_pct,mem_usage,mem_pct,net_io,block_io,pids" > "$out"
      snapshot "$out" "single"
      echo "→ Бичигдлээ: $out"
      column -s, -t "$out"
      ;;
  esac
}

main "$@"
