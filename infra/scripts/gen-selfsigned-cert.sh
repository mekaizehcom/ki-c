#!/usr/bin/env bash
# Generate a self-signed cert for local/dev so nginx can serve HTTPS.
set -euo pipefail
CERT_DIR="$(cd "$(dirname "$0")/../certs" && pwd)"
DOMAIN="${TESSA_DOMAIN:-localhost}"

if [[ -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]]; then
  echo "[cert] self-signed cert already exists in $CERT_DIR"
  exit 0
fi

openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem" \
  -subj "/CN=${DOMAIN}" \
  -addext "subjectAltName=DNS:${DOMAIN},DNS:localhost,IP:127.0.0.1"

echo "[cert] generated self-signed cert for ${DOMAIN} in $CERT_DIR"
