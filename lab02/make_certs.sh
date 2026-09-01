#!/usr/bin/env bash
# CNC302 Лаб 2 — mTLS-д зориулсан CA болон төхөөрөмжийн сертификат үүсгэнэ.
#
#   bash make_certs.sh init                  # CA + серверийн сертификат
#   bash make_certs.sh device dev0001        # нэг төхөөрөмжийн сертификат
#   bash make_certs.sh device dev0002 dev0003
#   bash make_certs.sh revoke dev0002        # хүчингүй болгох (CRL)
#   bash make_certs.sh list
#
# АНХААР: эдгээр түлхүүрүүд ЗӨВХӨН лабораторид зориулагдсан. .gitignore-д
# бүртгэгдсэн — commit хийхийг оролдвол таны тайлан 0 оноо авна.

set -euo pipefail

CERTDIR="${CERTDIR:-$(cd "$(dirname "$0")" && pwd)/certs}"
DAYS_CA=1825
DAYS_LEAF=365
SUBJ_BASE="/C=MN/ST=Ulaanbaatar/O=MUST/OU=CNC302"
# Pi-гийн хостын нэрийг өөрийнхөөрөө солино!
SERVER_CN="${SERVER_CN:-pi-team03.local}"

mkdir -p "$CERTDIR"
cd "$CERTDIR"

init_ca() {
  if [ -f ca.crt ]; then echo "CA аль хэдийн байна: $CERTDIR/ca.crt"; return; fi
  echo "→ CA үүсгэж байна…"
  openssl genrsa -out ca.key 4096 2>/dev/null
  openssl req -x509 -new -nodes -key ca.key -sha256 -days "$DAYS_CA" \
    -subj "${SUBJ_BASE}/CN=CNC302 Lab CA" -out ca.crt

  echo "→ Серверийн (брокерийн) сертификат: CN=${SERVER_CN}"
  openssl genrsa -out server.key 2048 2>/dev/null
  openssl req -new -key server.key -subj "${SUBJ_BASE}/CN=${SERVER_CN}" -out server.csr
  cat > server.ext <<EOF
subjectAltName = DNS:${SERVER_CN}, DNS:localhost, IP:127.0.0.1
extendedKeyUsage = serverAuth
EOF
  openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out server.crt -days "$DAYS_LEAF" -sha256 -extfile server.ext
  rm -f server.csr server.ext
  touch index.txt; echo 1000 > crlnumber
  echo "→ Бэлэн: ca.crt, server.crt, server.key"
}

make_device() {
  local id="$1"
  echo "→ Төхөөрөмжийн сертификат: CN=${id}"
  openssl genrsa -out "${id}.key" 2048 2>/dev/null
  openssl req -new -key "${id}.key" -subj "${SUBJ_BASE}/CN=${id}" -out "${id}.csr"
  cat > "${id}.ext" <<EOF
extendedKeyUsage = clientAuth
EOF
  openssl x509 -req -in "${id}.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out "${id}.crt" -days "$DAYS_LEAF" -sha256 -extfile "${id}.ext"
  rm -f "${id}.csr" "${id}.ext"
  # ThingsBoard-д оруулах PEM (сертификатын агуулга)
  openssl x509 -in "${id}.crt" -noout -fingerprint -sha256 | tee "${id}.fingerprint"
}

case "${1:-help}" in
  init) init_ca ;;
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
    echo "→ ${id} хүчингүй болголоо (файлыг .revoked болгож нэрлэв)."
    echo "  ThingsBoard/EMQX дээр итгэмжлэлийг гараар устгахаа мартуузай." ;;
  *) sed -n '2,14p' "$0" ;;
esac
