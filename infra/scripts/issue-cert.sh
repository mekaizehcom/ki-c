#!/usr/bin/env bash
# Issue a real Let's Encrypt cert for tessa.ki-c.pro (production).
# Requires: DNS A record tessa.ki-c.pro -> this host, ports 80/443 open,
# and the prod stack running (nginx serving the ACME webroot).
set -euo pipefail
DOMAIN="${TESSA_DOMAIN:-tessa.ki-c.pro}"
EMAIL="${CERT_EMAIL:-admin@${DOMAIN}}"

cd "$(dirname "$0")/../.."

docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm \
  --entrypoint certbot certbot certonly \
  --webroot -w /var/www/certbot \
  -d "${DOMAIN}" \
  --email "${EMAIL}" --agree-tos --no-eff-email --non-interactive

echo "[cert] issued for ${DOMAIN}; reloading nginx"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec nginx nginx -s reload
