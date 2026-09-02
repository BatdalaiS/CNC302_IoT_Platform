#!/usr/bin/env bash
# CNC302 Лаб 5 — Эвдрэлийн зориудын үүсгэлт (failure injection)
#
# Стек хоёр хостод хуваагдсан тул эвдрэл ч хоёр газар үүснэ:
#
#   RASPBERRY PI 3B ДЭЭР :  uplink-down | uplink-up | broker | cpu | disk
#   ЗӨӨВРИЙН КОМПЬЮТЕР   :  influx
#   Хаана ч             :  restore   (өөрийн үүсгэсэн бүхнийг буцаана)
#
# ── ХАМГИЙН ЧУХАЛ ЭВДРЭЛ: uplink-down ───────────────────────────────────────
# Pi → зөөврийн компьютер хоорондын 1883 портыг таслана. Ирмэгийн mosquitto
# ажилласаар байх ба гүүр (bridge) нь мессежийг ДИСКЭНД дараалуулна
# (store-and-forward). Уплинк сэргэхэд дараалал урсаж эхэлнэ. Store-and-forward
# ажиллаж байгаа эсэхийг ЯГ ЭНЭ ГОРИМООР л хэмждэг.
#
#   bash failure_inject.sh uplink-down 60   # 60 сек таслаад автоматаар сэргээнэ
#   bash failure_inject.sh uplink-down 0    # тасалж орхино (гараар uplink-up)
#   bash failure_inject.sh uplink-up        # хаалтыг авна
#   bash failure_inject.sh broker 30        # ирмэгийн mosquitto-г дахин асаана
#   bash failure_inject.sh cpu 45           # Pi-гийн 4 цөмийг ачаална
#   bash failure_inject.sh disk 60          # диск дүүргэлт (АЮУЛГҮЙ, давталт)
#   bash failure_inject.sh influx 30        # ҮҮЛ дээр: InfluxDB-г зогсооно
#   bash failure_inject.sh network 30       # хуучин нэр = uplink-down
#   bash failure_inject.sh restore          # БҮХ зүйлийг буцаана
#
# ── АЮУЛГҮЙ БАЙДЛЫН ДҮРЭМ ───────────────────────────────────────────────────
#   · Устгах үйлдэл бүр эхлэхээсээ ӨМНӨ юу хийхээ хэвлэнэ.
#   · Бүх үйлдэл БУЦААХ БОЛОМЖТОЙ. `restore` нь бидний нэмсэн iptables/nft
#     дүрмийг ч устгана.
#   · `disk` горим нь microSD-гийн БОДИТ дискийг хэзээ ч дүүргэхгүй.
#     512 MiB-ийн давталтын (loopback) файлын систем үүсгэж, түүнийг дүүргэнэ.
#     Pi 3B-гийн microSD-г элээх нь хичээлийн зорилго БИШ.

set -u

MODE="${1:-}"
DUR="${2:-30}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
EDGE_COMPOSE="$REPO_DIR/edge/docker-compose.yml"
CLOUD_COMPOSE="$REPO_DIR/stack/docker-compose.yml"
EDGE_ENV="$REPO_DIR/edge/.env"

LOOPDIR="/tmp/cnc302-smalldisk"
LOOPIMG="/tmp/cnc302-smalldisk.img"
OUTDIR="$REPO_DIR/lab05/out"
LOG="$OUTDIR/failure-log.txt"
STATE="$OUTDIR/.uplink-state"      # ямар хаалт тавьсныг санана: iptables|nft

mkdir -p "$OUTDIR"
note() { echo "$(date -Is)  $*" | tee -a "$LOG"; }
announce() { echo ""; echo "  ┌─ ХИЙХ ГЭЖ БУЙ ҮЙЛДЭЛ ─────────────────────────"; \
             echo "  │ $*"; echo "  └───────────────────────────────────────────────"; }

usage() { sed -n '2,32p' "$0"; }

t0=$(date +%s)
elapsed() { echo $(( $(date +%s) - t0 )); }

# ── Үүлний хаяг: edge/.env-ээс уншина (гүүр яг тэр рүү холбогддог) ──────────
CLOUD_HOST=""
CLOUD_PORT="1883"
if [ -f "$EDGE_ENV" ]; then
  CLOUD_HOST=$(awk -F= '/^CLOUD_HOST=/{gsub(/[" ]/,"",$2); print $2}' "$EDGE_ENV" | tail -1)
  p=$(awk -F= '/^CLOUD_PORT=/{gsub(/[" ]/,"",$2); print $2}' "$EDGE_ENV" | tail -1)
  [ -n "${p:-}" ] && CLOUD_PORT="$p"
fi
CLOUD_HOST="${CLOUD_HOST_OVERRIDE:-$CLOUD_HOST}"

# ─────────────────────────── УПЛИНКИЙГ ТАСЛАХ ───────────────────────────
# Зорилго: Pi-гээс ҮҮЛ РҮҮ гарах 1883 холболтыг л таслах. Локал 1883
# (төхөөрөмж → Pi, агент → Pi) ажилласаар байх ЁСТОЙ — эс бөгөөс энэ нь
# "уплинк тасарсан" биш, "бүх зүйл унасан" туршилт болно.

iptables_ok() { command -v iptables >/dev/null 2>&1; }
nft_ok()      { command -v nft >/dev/null 2>&1; }

# sudo хэрэгтэй эсэхийг тодорхойлно (root бол шууд).
SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

uplink_down() {
  if [ -z "$CLOUD_HOST" ]; then
    echo "✗ CLOUD_HOST олдсонгүй ($EDGE_ENV дотор байх ёстой)." >&2
    echo "  Хаягийг гараар өгч болно:  CLOUD_HOST_OVERRIDE=192.168.1.100 bash $0 uplink-down 60" >&2
    exit 1
  fi
  if [ -f "$STATE" ]; then
    note "  (уплинк аль хэдийн тасарсан байна — давхар тавихгүй)"
    return 0
  fi

  announce "Pi → ${CLOUD_HOST}:${CLOUD_PORT} чиглэлийн TCP-г ХААНА (уплинк тасрана).
  │ Локал 1883 хөндөгдөхгүй: төхөөрөмжүүд Pi рүү нийтэлсээр байна.
  │ Гүүр мессежийг дискэнд дараалуулж эхлэх ёстой (store-and-forward).
  │ Буцаах:  bash $0 uplink-up   эсвэл   bash $0 restore"

  if iptables_ok && $SUDO iptables -I OUTPUT -p tcp -d "$CLOUD_HOST" \
       --dport "$CLOUD_PORT" -j DROP 2>/dev/null; then
    echo "iptables" > "$STATE"
    note "▼ Уплинк тасарлаа (iptables OUTPUT DROP → $CLOUD_HOST:$CLOUD_PORT)"
    return 0
  fi

  if nft_ok \
     && $SUDO nft add table inet cnc302 2>/dev/null \
     && $SUDO nft add chain inet cnc302 out \
          '{ type filter hook output priority 0 ; }' 2>/dev/null \
     && $SUDO nft add rule inet cnc302 out ip daddr "$CLOUD_HOST" \
          tcp dport "$CLOUD_PORT" drop 2>/dev/null; then
    echo "nft" > "$STATE"
    note "▼ Уплинк тасарлаа (nft inet cnc302 → $CLOUD_HOST:$CLOUD_PORT)"
    return 0
  fi

  echo "" >&2
  echo "✗ УПЛИНКИЙГ ТАСЛАЖ ЧАДСАНГҮЙ." >&2
  echo "  iptables ч, nft ч ажиллуулах эрх алга (эсвэл суугаагүй)." >&2
  echo "  Хийж болох зүйл:" >&2
  echo "    1) sudo эрхтэйгээр дахин ажиллуулна:  sudo bash $0 uplink-down $DUR" >&2
  echo "    2) sudo apt install -y iptables" >&2
  echo "    3) Эрх байхгүй бол Ethernet кабелиа 30 сек салгаж, гараар тэмдэглэ —" >&2
  echo "       үр дүн ижил, зөвхөн автоматжуулалт л алдагдана." >&2
  echo "  ЮУ Ч ӨӨРЧЛӨГДСӨНГҮЙ (систем хэвийн хэвээр)." >&2
  exit 3
}

uplink_up() {
  if [ ! -f "$STATE" ]; then
    note "  (уплинкийн хаалт байхгүй — хийх зүйлгүй)"
    return 0
  fi
  local kind; kind=$(cat "$STATE" 2>/dev/null || echo "")
  announce "Уплинкийн хаалтыг АВНА ($kind). Гүүр дахин холбогдож,
  │ дараалалд хуримтлагдсан мессежээ үүл рүү урсгаж эхэлнэ."
  case "$kind" in
    iptables)
      $SUDO iptables -D OUTPUT -p tcp -d "$CLOUD_HOST" \
        --dport "$CLOUD_PORT" -j DROP 2>/dev/null || \
        note "  ⚠ iptables дүрэм олдсонгүй (аль хэдийн устсан байж болно)"
      ;;
    nft)
      $SUDO nft delete table inet cnc302 2>/dev/null || \
        note "  ⚠ nft хүснэгт олдсонгүй (аль хэдийн устсан байж болно)"
      ;;
    *)
      note "  ⚠ Төлөвийн файл ойлгомжгүй: '$kind'" ;;
  esac
  rm -f "$STATE"
  note "▲ Уплинк сэргэлээ."
  note "  Одоо шалга: mosquitto_sub -h localhost -t 'cnc302/+/+/+/+/bridge/state' -C 1"
  note "  (1 = гүүр холбогдсон)"
}

# ─────────────────────────────── ГОРИМУУД ───────────────────────────────

case "$MODE" in

  uplink-down|network)
    if [ "$MODE" = "network" ]; then
      note "  ('network' нь хуучин нэр — uplink-down руу шилжүүлэв)"
    fi
    uplink_down
    if [ "$DUR" != "0" ]; then
      note "  ${DUR} секунд хүлээж байна… (Ctrl+C дарвал хаалт ҮЛДЭНЭ — restore хий)"
      sleep "$DUR"
      uplink_up
      note "▲ Мөчлөг дууслаа. Нийт: $(elapsed) сек"
    else
      note "  DUR=0 тул хаалт үлдлээ. Буцаах:  bash $0 uplink-up"
    fi
    ;;

  uplink-up)
    uplink_up
    ;;

  broker)
    announce "Ирмэгийн mosquitto-г ${DUR} секунд ЗОГСООНО.
  │ Төхөөрөмжүүд Pi руу нийтэлж чадахаа болино. Гүүр ч зогсоно.
  │ Өгөгдөл хаана буферлэгдэх вэ? (Хариулт: төхөөрөмж өөрөө кодлогдсон бол.)
  │ Буцаах: энэ скрипт өөрөө дахин асаана; эс бөгөөс bash $0 restore"
    note "▼ Ирмэгийн mosquitto зогсоолоо (${DUR}s)"
    docker compose -f "$EDGE_COMPOSE" stop mosquitto
    sleep "$DUR"
    note "▲ mosquitto-г сэргээж байна"
    docker compose -f "$EDGE_COMPOSE" start mosquitto
    note "  ажиллаж эхлэх хүртэл хүлээж байна…"
    for _ in $(seq 1 30); do
      st=$(docker inspect -f '{{.State.Status}}' cnc302-mosquitto 2>/dev/null || echo "")
      [ "$st" = "running" ] && break
      sleep 2
    done
    note "▲ mosquitto сэргэлээ. Нийт: $(elapsed) сек"
    ;;

  influx)
    if [ ! -f "$CLOUD_COMPOSE" ]; then
      echo "✗ $CLOUD_COMPOSE олдсонгүй." >&2; exit 1
    fi
    if ! docker ps -a --format '{{.Names}}' | grep -q '^cnc302-influxdb$'; then
      echo "" >&2
      echo "✗ cnc302-influxdb энэ хост дээр алга." >&2
      echo "  InfluxDB нь ЗӨӨВРИЙН КОМПЬЮТЕР дээр ажилладаг (үүлний давхарга)." >&2
      echo "  Энэ горимыг тэнд ажиллуулна уу:  bash lab05/failure_inject.sh influx $DUR" >&2
      exit 1
    fi
    announce "ҮҮЛ дээрх InfluxDB-г ${DUR} секунд ЗОГСООНО.
  │ Брокер болон гүүр ажилласаар байна — зөвхөн БИЧИХ давхарга унана.
  │ Node-RED-ийн dead-letter файл ажиллаж байгаа эсэхийг ажигла.
  │ Буцаах: энэ скрипт өөрөө дахин асаана."
    note "▼ InfluxDB зогсоолоо (${DUR}s)"
    docker compose -f "$CLOUD_COMPOSE" stop influxdb
    sleep "$DUR"
    note "▲ InfluxDB-г сэргээж байна"
    docker compose -f "$CLOUD_COMPOSE" --profile core start influxdb
    note "▲ Сэргэлээ. Нийт: $(elapsed) сек"
    ;;

  disk)
    announce "АЮУЛГҮЙ дискний туршилт: 512 MiB-ийн ДАВТАЛТЫН файл үүсгэж,
  │ ЗӨВХӨН түүнийг дүүргэнэ. Pi-гийн БОДИТ microSD хөндөгдөхгүй.
  │ Үүсэх файлууд: $LOOPIMG  →  $LOOPDIR дээр холбогдоно.
  │ Буцаах: umount + файлыг устгана (энэ скрипт өөрөө хийнэ)."
    note "▼ Дискний дүүргэлтийн туршилт (${DUR}s) — АЮУЛГҮЙ, 512 MiB давталт"
    if [ ! -f "$LOOPIMG" ]; then
      dd if=/dev/zero of="$LOOPIMG" bs=1M count=512 status=none
      mkfs.ext4 -q "$LOOPIMG"
    fi
    $SUDO mkdir -p "$LOOPDIR"
    if ! $SUDO mount -o loop "$LOOPIMG" "$LOOPDIR"; then
      echo "✗ mount амжилтгүй (sudo эрх эсвэл loop модуль дутуу). Юу ч өөрчлөгдсөнгүй." >&2
      exit 3
    fi
    note "  512 MiB файлын систем холбогдлоо: $LOOPDIR"
    note "  дүүргэж байна…"
    $SUDO dd if=/dev/zero of="$LOOPDIR/filler" bs=1M status=none 2>/dev/null || true
    df -h "$LOOPDIR" | tee -a "$LOG"
    note "  ⚠ Одоо Docker-ийн лог хязгаарыг шалга: docker inspect ... LogConfig"
    note "  (Pi 3B дээр microSD дүүрэх нь хамгийн хортой эвдрэл — бүх давхарга нэгэн зэрэг унана)"
    sleep "$DUR"
    note "▲ Дискийг чөлөөлж байна"
    $SUDO rm -f "$LOOPDIR/filler"
    $SUDO umount "$LOOPDIR" 2>/dev/null || true
    note "▲ Сэргэлээ"
    ;;

  cpu)
    CORES=$(nproc)
    announce "Pi-гийн ${CORES} цөмийг ${DUR} секунд 100% ачаална (stress-ng).
  │ САНАМЖ: 4×Cortex-A53-ыг бүтэн ачаалахад ТЕМПЕРАТУР огцом өснө. Хөргөлт
  │ сул бол vcgencmd get_throttled нь 0x0 биш болж, процессор удаашрана.
  │ ЭНЭ ӨӨРӨӨ ХИЧЭЭЛИЙН СУРГАМЖ: ирмэгийн техник хангамжийн хязгаар нь
  │ зөвхөн CPU-гийн хурд биш, ДУЛААНЫ ТӨСӨВ ч мөн юм.
  │ Буцаах: stress-ng хугацаа дуусангуут өөрөө зогсоно."
    if ! command -v stress-ng >/dev/null 2>&1; then
      echo "✗ stress-ng суугаагүй:  sudo apt install -y stress-ng" >&2
      exit 1
    fi
    note "  өмнөх төлөв: $(vcgencmd get_throttled 2>/dev/null || echo 'throttled=n/a')  $(vcgencmd measure_temp 2>/dev/null || echo 'temp=n/a')"
    note "▼ CPU-г ${CORES} урсгалаар 100% ачааллаа (${DUR}s)"
    stress-ng --cpu "$CORES" --timeout "${DUR}s" --metrics-brief 2>&1 | tee -a "$LOG"
    note "  дараах төлөв: $(vcgencmd get_throttled 2>/dev/null || echo 'throttled=n/a')  $(vcgencmd measure_temp 2>/dev/null || echo 'temp=n/a')"
    note "▲ Ачаалал дууслаа. Throttle 0x0 биш болсон бол ТАЙЛАНД БИЧ."
    ;;

  restore)
    announce "Энэ скриптийн үүсгэсэн БҮХ өөрчлөлтийг буцаана:
  │  · уплинкийн iptables/nft хаалт
  │  · зогссон ирмэгийн mosquitto
  │  · зогссон үүлний InfluxDB (энэ хост дээр байгаа бол)
  │  · давталтын дискний файл ба түүний холболт"
    note "▲ Бүх зүйлийг сэргээж байна"
    uplink_up
    docker compose -f "$EDGE_COMPOSE" start mosquitto 2>/dev/null || true
    docker compose -f "$CLOUD_COMPOSE" --profile core start emqx influxdb 2>/dev/null || true
    $SUDO umount "$LOOPDIR" 2>/dev/null || true
    rm -f "$LOOPIMG"
    rm -f "$STATE"
    note "▲ Сэргээлт дууслаа. Одоогийн төлөв:"
    docker compose -f "$EDGE_COMPOSE" ps 2>/dev/null || true
    docker compose -f "$CLOUD_COMPOSE" ps 2>/dev/null || true
    if iptables_ok; then
      echo "  Үлдсэн iptables дүрэм (хоосон байх ёстой):"
      $SUDO iptables -S OUTPUT 2>/dev/null | grep -- "--dport $CLOUD_PORT" || echo "    (алга — зөв)"
    fi
    ;;

  ""|-h|--help)
    usage; exit 0 ;;

  *)
    echo "Танихгүй горим: $MODE" >&2
    usage; exit 1 ;;
esac
