# Deployment

## Environments
- **dev**: `docker compose up` (auto-merges `docker-compose.override.yml`):
  source hot-reload, API:8000 & web:5173 exposed, self-signed TLS.
- **prod**: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`:
  baked images, only nginx exposes 80/443, Let's Encrypt + certbot renewer.

## First production deploy on tessa.ki-c.pro
1. `git clone` the repo to `/home/ubuntu/tessa`.
2. `cp .env.example .env` and set strong `SECRET_KEY`, `FERNET_KEY`,
   `POSTGRES_PASSWORD`, `LITELLM_MASTER_KEY`, `BOOTSTRAP_ADMIN_PASSWORD`.
3. Point DNS `A tessa.ki-c.pro -> <host IP>`; open security-group 80/443.
4. `make prod` (brings stack up; nginx serves self-signed until cert issued).
5. `make cert` → issues Let's Encrypt cert, reloads nginx.
6. First login as bootstrap superadmin → scan TOTP QR.

## Migrations
API entrypoint runs `alembic upgrade head` then an idempotent seed on every
start. New migrations go in `services/api/migrations/versions/`.

## CI/CD (Phase 7)
GitHub Actions: lint + tests + docker build on push; optional GHCR publish.

## Optional systemd
`infra/systemd/tessa.service` runs the prod stack as a unit.
