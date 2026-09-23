#!/usr/bin/env bash
# CNC302 Лаб 2 — mTLS-д зориулсан CA болон төхөөрөмжийн сертификат үүсгэнэ.
#
#   CLOUD_HOST=192.168.1.100 bash make_certs.sh init   # CA + брокерийн сертификат
#   bash make_certs.sh device dev0001        # нэг төхөөрөмжийн сертификат
#   bash make_certs.sh device dev0002 dev0003
#   bash make_certs.sh revoke dev0002        # файлыг .revoked болгоно (CRL БИШ)
#   bash make_certs.sh list
#
# Серверийн сертификат нь ЗӨӨВРИЙН КОМПЬЮТЕР дээрх EMQX-д зориулагдана.
# Клиент (mosquitto_pub, paho) холбогдсон хаягаа subjectAltName (SAN)-тай
# тулгадаг тул Pi-гаас холбогдох хаяг (компьютерийн LAN IP = CLOUD_HOST)
# SAN-д заавал орно. IP солигдвол:
#   CLOUD_HOST=<шинэ IP> bash make_certs.sh server
#
# АНХААР: эдгээр түлхүүрүүд ЗӨВХӨН лабораторид зориулагдсан. .gitignore-д
# бүртгэгдсэн — commit хийхийг оролдвол таны тайлан 0 оноо авна.

set -euo pipefail

SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
CERTDIR="${CERTDIR:-$(dirname "$SELF")/certs}"
DAYS_CA=1825
DAYS_LEAF=365
SUBJ_BASE="/C=MN/ST=Ulaanbaatar/O=MUST/OU=CNC302"
# Брокер (EMQX) зөөврийн компьютер дээр ажиллана — Pi дээр биш.
SERVER_CN="${SERVER_CN:-cnc302-cloud}"
# Pi-гаас холбогдох хаяг: компьютерийн LAN IP (edge/.env-ийн CLOUD_HOST) эсвэл DNS нэр
CLOUD_HOST="${CLOUD_HOST:-}"

mkdir -p "$CERTDIR"
cd "$CERTDIR"

init_ca() {
  if [ -f ca.crt ]; then echo "CA аль хэдийн байна: $CERTDIR/ca.crt"; return; fi
  echo "→ CA үүсгэж байна…"
  openssl genrsa -out ca.key 4096 2>/dev/null
  openssl req -x509 -new -nodes -key ca.key -sha256 -days "$DAYS_CA" \
    -subj "${SUBJ_BASE}/CN=CNC302 Lab CA" -out ca.crt
  make_server
}

make_server() {
  local san="DNS:${SERVER_CN}, DNS:localhost, DNS:emqx, IP:127.0.0.1"
  if [ -z "$CLOUD_HOST" ]; then
    echo "⚠ CLOUD_HOST хоосон: SAN-д зөвхөн localhost/127.0.0.1 орно."
    echo "  Pi-гаас 8883-т холбогдоход 'host name verification failed' гарна."
    echo "  Засах: CLOUD_HOST=<компьютерийн LAN IP> bash make_certs.sh server"
  elif [[ "$CLOUD_HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    san="${san}, IP:${CLOUD_HOST}"
  else
    san="${san}, DNS:${CLOUD_HOST}"
  fi
  echo "→ Серверийн (брокерийн) сертификат: CN=${SERVER_CN}"
  echo "  SAN: ${san}"
  openssl genrsa -out server.key 2048 2>/dev/null
  openssl req -new -key server.key -subj "${SUBJ_BASE}/CN=${SERVER_CN}" -out server.csr
  printf 'subjectAltName = %s\nextendedKeyUsage = serverAuth\n' "$san" > server.ext
  openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days "$DAYS_LEAF" -sha256 -extfile server.ext
  rm -f server.csr server.ext
  echo "→ Бэлэн: ca.crt, server.crt, server.key"
}

make_device() {
  local id="$1"
  echo "→ Төхөөрөмжийн сертификат: CN=${id}"
  openssl genrsa -out "${id}.key" 2048 2>/dev/null
  openssl req -new -key "${id}.key" -subj "${SUBJ_BASE}/CN=${id}" -out "${id}.csr"
  printf 'extendedKeyUsage = clientAuth\n' > "${id}.ext"
  openssl x509 -req -in "${id}.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out "${id}.crt" -days "$DAYS_LEAF" -sha256 -extfile "${id}.ext"
  rm -f "${id}.csr" "${id}.ext"
  # SHA-256 хурууны хээ — платформ (жишээ нь ThingsBoard) дээр төхөөрөмжийг таних
  openssl x509 -in "${id}.crt" -noout -fingerprint -sha256 | tee "${id}.fingerprint"
}

case "${1:-help}" in
  init) init_ca ;;
  server)
    [ -f ca.crt ] || { echo "Эхлээд: bash make_certs.sh init"; exit 1; }
    make_server ;;
  device)
    shift; [ $# -ge 1 ] || { echo "Төхөөрөмжийн ID заана уу"; exit 1; }
    [ -f ca.crt ] || init_ca
    for id in "$@"; do make_device "$id"; done ;;
  list)
    ls -1 *.crt 2>/dev/null | while read -r f; do
      printf '%-16s  дуусах: %s\n' "$f" \
        "$(openssl x509 -in "$f" -noout -enddate | cut -d= -f2)"
    done ;;
  revoke)
    shift; id="${1:?ID}"
    mv "${id}.crt" "${id}.crt.revoked"; mv "${id}.key" "${id}.key.revoked"
    echo "→ ${id}: файлыг .revoked болгож нэрлэв."
    echo "  АНХААР: энэ нь CRL БИШ. Сертификат өөрөө ${DAYS_LEAF} хоног хүчинтэй хэвээр,"
    echo "  EMQX түүнийг таньсаар байна. EMQX-ийн CRL шалгалт нь сертификат доторх"
    echo "  CRL Distribution Point URL-аас CRL татдаг (docs.emqx.com → CRL Check)." ;;
  *) sed -n '2,17p' "$SELF" ;;
esac
