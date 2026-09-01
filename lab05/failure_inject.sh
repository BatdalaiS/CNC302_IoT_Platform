#!/usr/bin/env bash
# CNC302 Лаб 5 — Эвдрэлийн зориудын үүсгэлт (failure injection)
#
# Raspberry Pi ДЭЭР ажиллуулна. data_integrity.py publish зэрэг ажиллаж байх ёстой.
#
#   bash failure_inject.sh broker 30      # брокерыг 30 сек зогсооно
#   bash failure_inject.sh network 30     # брокерыг сүлжээнээс салгана
#   bash failure_inject.sh disk 60        # InfluxDB-ийн дискийг дүүргэнэ (АЮУЛГҮЙ)
#   bash failure_inject.sh cpu 45         # CPU-г 100% ачаална
#   bash failure_inject.sh influx 30      # цаг цувааны санг зогсооно
#   bash failure_inject.sh restore        # бүх зүйлийг сэргээнэ
#
# АЮУЛГҮЙ БАЙДАЛ: `disk` горим нь Pi-гийн бодит дискийг дүүргэхгүй.
# 512 MiB-ийн давталтын (loopback) файлын систем үүсгэж, тэр дотор
# InfluxDB-ийн бичих фолдерыг холбож дүүргэнэ.

set -euo pipefail

MODE="${1:?горим: broker|network|disk|cpu|influx|restore}"
DUR="${2:-30}"
NET="cnc302_default"
LOOPDIR="/tmp/cnc302-smalldisk"
LOOPIMG="/tmp/cnc302-smalldisk.img"
LOG="lab05/out/failure-log.txt"

mkdir -p "$(dirname "$LOG")"
note() { echo "$(date -Is)  $*" | tee -a "$LOG"; }

t0=$(date +%s.%N)

case "$MODE" in

  broker)
    note "▼ EMQX-ийг зогсоолоо (${DUR}s)"
    docker compose -f stack/docker-compose.yml stop emqx
    sleep "$DUR"
    note "▲ EMQX-ийг сэргээж байна"
    docker compose -f stack/docker-compose.yml --profile core start emqx
    note "  healthy болтол хүлээж байна…"
    until [ "$(docker inspect -f '{{.State.Health.Status}}' cnc302-emqx)" = "healthy" ]; do
      sleep 2
    done
    note "▲ EMQX сэргэлээ. Нийт: $(echo "$(date +%s.%N) - $t0" | bc) сек"
    ;;

  network)
    note "▼ EMQX-ийг сүлжээнээс салгалаа (${DUR}s)"
    docker network disconnect "$NET" cnc302-emqx || \
      docker network disconnect bridge cnc302-emqx
    sleep "$DUR"
    note "▲ Сүлжээг сэргээж байна"
    docker network connect "$NET" cnc302-emqx || \
      docker network connect bridge cnc302-emqx
    note "▲ Сэргэлээ. Нийт: $(echo "$(date +%s.%N) - $t0" | bc) сек"
    ;;

  influx)
    note "▼ InfluxDB-г зогсоолоо (${DUR}s) — брокер ажиллаж байна!"
    docker compose -f stack/docker-compose.yml stop influxdb
    sleep "$DUR"
    note "▲ InfluxDB-г сэргээж байна"
    docker compose -f stack/docker-compose.yml --profile core start influxdb
    note "▲ Сэргэлээ. Нийт: $(echo "$(date +%s.%N) - $t0" | bc) сек"
    ;;

  disk)
    note "▼ Дискний дүүргэлтийн туршилт (${DUR}s) — АЮУЛГҮЙ, 512 MiB davталт"
    if [ ! -f "$LOOPIMG" ]; then
      dd if=/dev/zero of="$LOOPIMG" bs=1M count=512 status=none
      mkfs.ext4 -q "$LOOPIMG"
    fi
    sudo mkdir -p "$LOOPDIR"
    sudo mount -o loop "$LOOPIMG" "$LOOPDIR"
    note "  512 MiB файлын систем холбогдлоо: $LOOPDIR"
    note "  дүүргэж байна…"
    sudo dd if=/dev/zero of="$LOOPDIR/filler" bs=1M status=none 2>/dev/null || true
    df -h "$LOOPDIR" | tee -a "$LOG"
    note "  ⚠ Одоо Docker-ийн лог хязгаарыг шалга: docker inspect ... LogConfig"
    sleep "$DUR"
    note "▲ Дискийг чөлөөлж байна"
    sudo rm -f "$LOOPDIR/filler"
    sudo umount "$LOOPDIR" || true
    note "▲ Сэргэлээ"
    ;;

  cpu)
    CORES=$(nproc)
    note "▼ CPU-г ${CORES} урсгалаар 100% ачааллаа (${DUR}s)"
    command -v stress-ng >/dev/null || { echo "stress-ng суулгана уу: sudo apt install stress-ng"; exit 1; }
    stress-ng --cpu "$CORES" --timeout "${DUR}s" --metrics-brief 2>&1 | tee -a "$LOG"
    note "▲ Ачаалал дууслаа"
    ;;

  restore)
    note "▲ Бүх зүйлийг сэргээж байна"
    docker network connect "$NET" cnc302-emqx 2>/dev/null || true
    docker compose -f stack/docker-compose.yml --profile core start emqx influxdb 2>/dev/null || true
    sudo umount "$LOOPDIR" 2>/dev/null || true
    rm -f "$LOOPIMG"
    docker compose -f stack/docker-compose.yml ps
    ;;

  *)
    sed -n '2,18p' "$0"; exit 1 ;;
esac
