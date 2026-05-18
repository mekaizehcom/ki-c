#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] waiting for postgres at ${POSTGRES_HOST}:${POSTGRES_PORT} ..."
for i in $(seq 1 30); do
  if python -c "import socket,os,sys; s=socket.socket(); s.settimeout(2); s.connect((os.environ['POSTGRES_HOST'], int(os.environ['POSTGRES_PORT']))); s.close()" 2>/dev/null; then
    echo "[entrypoint] postgres reachable"; break
  fi
  echo "[entrypoint] postgres not ready ($i)"; sleep 2
done

echo "[entrypoint] running migrations ..."
alembic -c /srv/alembic.ini upgrade head

echo "[entrypoint] seeding bootstrap superadmin (idempotent) ..."
python -m app.seed || echo "[entrypoint] seed skipped/failed (non-fatal)"

echo "[entrypoint] starting: $*"
exec "$@"
