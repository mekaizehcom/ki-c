#!/usr/bin/env bash
# One-shot local bootstrap: .env, self-signed cert, build & start dev stack.
set -euo pipefail
cd "$(dirname "$0")/../.."

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[bootstrap] created .env from .env.example — review secrets before prod!"
fi

bash infra/scripts/gen-selfsigned-cert.sh

echo "[bootstrap] building and starting dev stack ..."
docker compose up -d --build

echo "[bootstrap] done. Web: http://localhost  (or https://localhost, self-signed)"
echo "[bootstrap] API health: http://localhost/api/health"
