# Tessa — Tech Context

> Stack, Setup, Commands. Zum Nachschlagen — keine Erklärtexte.

## Stack-Übersicht

| Layer | Technologie | Version | Quelle |
|---|---|---|---|
| Backend | Python + FastAPI | 3.12 + 0.115 | `services/api/Dockerfile`, `requirements.txt` |
| Frontend | SvelteKit (Svelte 5) | 2.8 / 5.1 | `services/web/package.json` |
| RDBMS | PostgreSQL | 16 | `docker-compose.yml` |
| Vector DB | Qdrant | latest | dito |
| Cache/Queue | Redis | 7 | dito |
| Model Gateway | LiteLLM Proxy | main-latest | `infra/litellm/config.yaml` |
| Reverse Proxy | Nginx | latest | `infra/nginx/{dev,prod}.conf` |
| TLS | Let's Encrypt + certbot | | `infra/scripts/issue-cert.sh` |
| Auth | Argon2id (pw) + TOTP RFC-6238 | `argon2-cffi`, `pyotp` | `app/security.py` |
| Crypto-at-rest | Fernet (cryptography) | | `app/security.py:encrypt/decrypt` |
| Migrations | Alembic | 1.14 | `services/api/migrations/` |
| Tests | pytest | 8.3 | `services/api/tests/` |
| CI | GitHub Actions | | `.github/workflows/ci.yml` |
| Host OS | Ubuntu | 26.04 LTS | EC2 (54.76.15.82) |

## Repository-Layout

```
tessa/
├── docker-compose.yml             Basis
├── docker-compose.override.yml    Dev (auto-merge)
├── docker-compose.prod.yml        Prod (-f beide angeben)
├── .env / .env.example            Konfiguration (Secrets gitignored)
├── Makefile                       up/down/prod/cert/logs/test
├── README.md
├── services/api/                  FastAPI Backend (siehe systemPatterns.md)
├── services/web/                  SvelteKit Frontend
├── services/worker/               Ingestion-Worker (Redis brpop)
├── infra/
│   ├── nginx/{dev,prod}.conf
│   ├── litellm/config.yaml
│   ├── scripts/{bootstrap,issue-cert,gen-selfsigned-cert,backup}.sh
│   └── systemd/tessa.service
├── workspaces/company-default/    OpenClaw-Steering-Dateien
├── docs/                          architecture, security, deployment
├── memory-bank/                   ← DIESE Memory Bank
├── tests/                         (reserviert)
└── .github/workflows/ci.yml
```

## Lokale / Dev-Befehle

Auf dem Host ausgeführt (Docker hat passwordless sudo):

```bash
# Dev-Stack hoch (auto-merged override.yml)
sudo docker compose up -d --build
sudo docker compose ps
sudo docker compose logs -f tessa-api

# Tests (one-off Python 3.12 Container, hängt nicht vom api-Container ab)
sudo docker run --rm -v $PWD/services/api:/srv -w /srv python:3.12-slim \
  sh -c "pip install -q -r requirements.txt && python -m pytest -q -p no:warnings"

# Down
sudo docker compose down
```

## Prod-Befehle

```bash
# Prod-Stack (Internals NICHT öffentlich, nginx 80/443 only)
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Einzeldienst neu bauen + restart
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --no-deps --build tessa-api          # bzw. tessa-web / worker

# Logs
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  logs --tail=200 tessa-api | grep -v /api/health

# Let's Encrypt Cert ausstellen/erneuern
sudo CERT_EMAIL='kai@swiss-expert-services.com' TESSA_DOMAIN='tessa.ki-c.pro' \
  bash infra/scripts/issue-cert.sh
```

Auto-Renewal läuft im `tessa-certbot`-Container (Loop alle 12h).

## .env (auf der Maschine, gitignored)

`/home/ubuntu/tessa/.env` enthält:

- `TESSA_ENV=production`
- `TESSA_DOMAIN=tessa.ki-c.pro`, `PUBLIC_BASE_URL=https://tessa.ki-c.pro`
- `SECRET_KEY` — Session-Signing (itsdangerous)
- `FERNET_KEY` — verschlüsselt Provider-Keys/TOTP-Secrets/Integrations
- `POSTGRES_*` — DB-Zugang (User `tessa`, DB `tessa`)
- `REDIS_URL`, `QDRANT_URL`, `LITELLM_BASE_URL`, `LITELLM_MASTER_KEY`
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`
  (optional; können auch über Admin-UI verschlüsselt in DB)
- `EMBEDDING_PROVIDER` (`mock` oder `openai`), `EMBEDDING_MODEL`, `EMBEDDING_DIM`
- `BOOTSTRAP_ADMIN_*` — wird beim ersten Start verwendet, danach ignoriert
- `MODEL_NODE_1_URL`, `MODEL_NODE_2_URL` — externe lokale Modell-Nodes (optional)
- `BACKUP_PASSPHRASE` — AES-256-pbkdf2 für `infra/scripts/backup.sh`

`.env.example` ist im Repo und dokumentiert alle Schlüssel.

## Datenbank-Zugang (Debug / Migration)

```bash
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec -T postgres psql -U tessa -d tessa -c "\dt"

# Migration manuell (normalerweise via entrypoint.sh beim API-Start)
sudo docker compose ... exec tessa-api alembic -c /srv/alembic.ini upgrade head
```

## Externe Abhängigkeiten

| System | Wozu | Wie konfiguriert |
|---|---|---|
| OpenAI / Anthropic / DeepSeek | Modell-Provider | Admin-Panel oder `.env` |
| **SwissChat** (`https://swisschat.konnektai.pro`) | Chat-Kanal als Bot | Pairing-Code aus SwissChat-UI → `/admin` Pair-Button |
| Let's Encrypt | TLS für `tessa.ki-c.pro` | `infra/scripts/issue-cert.sh` |
| Lokale Modell-Nodes (Ollama/vLLM) | `local-private`-Profil | `MODEL_NODE_*_URL` in `.env`, **nicht** auf diesem Host (Spec §5.2) |

## Backup & Restore

```bash
# Backup (verschlüsselt)
BACKUP_PASSPHRASE='...' bash infra/scripts/backup.sh ./backups

# Restore (manuell)
openssl enc -d -aes-256-cbc -pbkdf2 -in tessa-YYYYMMDD-HHMMSS.tar.gz.enc \
  -pass env:BACKUP_PASSPHRASE | tar xz -C /tmp/restore
# dann postgres.sql in DB einspielen, qdrant-storage in Volume kopieren
```

Backup wird **nicht automatisiert** (Cron/systemd-timer nicht
installiert). Wenn das wichtig wird: einen Cron einrichten der das
Script läuft + Output offsite (S3 o.ä.).

## Netzwerk / Ports

- **Öffentlich:** 80 (Redirect), 443 (TLS).
- **Intern:** `tessa-internal` Bridge; postgres:5432, redis:6379,
  qdrant:6333, litellm:4000, tessa-api:8000, tessa-web:3000 —
  alle NUR im Netzwerk, nicht auf Host-Ports gemappt (im Prod-Overlay).

## Health & Monitoring

- `GET /api/health` — liveness (DB nicht angefasst)
- `GET /api/health/ready` — DB-Roundtrip
- `GET /api/health/metrics` — queue depth, worker heartbeat, user/conv/doc counts
- Container-Healthchecks: api, web, worker, postgres, redis
- Audit-Trail: `audit_logs`-Tabelle, im Admin-Panel "Recent audit"

## Bekannte Constraints

- **Host-Befehle wie `systemctl`/`docker`/`nginx` sind aus dem API-
  Container heraus nicht erreichbar.** Die Tools-Registry + Approval-
  Pipeline ist vollständig — aber die Execution würde `exit 127 not
  available here` melden. Lösung: dedizierter Host-Exec-Backend
  (z.B. SSH-Agent zu localhost mit eigenem Schlüssel + Whitelist).
  Bewusste v1-Limitation, dokumentiert in `docs/security.md`.
- Pydantic v2 — wenn ältere Beispiele auftauchen, auf `model_config =
  ConfigDict(...)` umstellen (kein `class Config` mehr).
