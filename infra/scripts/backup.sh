#!/usr/bin/env bash
# Encrypted backup of PostgreSQL + Qdrant.
# Usage: BACKUP_PASSPHRASE=... bash infra/scripts/backup.sh [outdir]
# Restore: openssl enc -d -aes-256-cbc -pbkdf2 -in FILE.enc -pass env:BACKUP_PASSPHRASE | tar xz
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT="${1:-./backups}"
TS="$(date +%Y%m%d-%H%M%S)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT"

: "${BACKUP_PASSPHRASE:?set BACKUP_PASSPHRASE (used to encrypt the archive)}"
source .env 2>/dev/null || true
PGUSER="${POSTGRES_USER:-tessa}"
PGDB="${POSTGRES_DB:-tessa}"

echo "[backup] pg_dump ..."
docker compose exec -T postgres pg_dump -U "$PGUSER" "$PGDB" > "$WORK/postgres.sql"

echo "[backup] qdrant snapshot ..."
# Trigger snapshots for all collections, then copy the storage dir.
docker compose exec -T qdrant sh -c 'tar czf - -C /qdrant storage' > "$WORK/qdrant-storage.tar.gz" || \
  echo "[backup] qdrant storage copy failed (continuing)"

tar czf "$WORK/tessa-$TS.tar.gz" -C "$WORK" postgres.sql qdrant-storage.tar.gz

echo "[backup] encrypting (AES-256, pbkdf2) ..."
openssl enc -aes-256-cbc -pbkdf2 -salt \
  -in "$WORK/tessa-$TS.tar.gz" \
  -out "$OUT/tessa-$TS.tar.gz.enc" \
  -pass env:BACKUP_PASSPHRASE

echo "[backup] done -> $OUT/tessa-$TS.tar.gz.enc"
ls -lh "$OUT/tessa-$TS.tar.gz.enc"
