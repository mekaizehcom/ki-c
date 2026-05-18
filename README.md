# Tessa — Internal AI Agent Platform

Central, controllable AI agent orchestrator for the company environment.
Primary instance: `https://tessa.ki-c.pro`.

OpenClaw-style steering files (`SOUL.md`, `AGENTS.md`, `TOOLS.md`, …) +
Web UI + SwissChat + username/password/TOTP login + multi-model gateway
(LiteLLM) + Qdrant vector memory + tool-permission & approval engine +
admin-configurable autonomy.

## Stack
FastAPI · SvelteKit · PostgreSQL 16 · Qdrant · Redis · LiteLLM · Nginx ·
Docker Compose · Ubuntu 24.04+.

## Quick start (local dev)
```bash
cp .env.example .env          # review secrets
bash infra/scripts/bootstrap.sh
# Web:  http://localhost        API health: http://localhost/api/health
```
First login as the bootstrap superadmin (`.env` BOOTSTRAP_ADMIN_*) → you'll be
prompted to scan a TOTP QR, then enter the code.

## Production (on tessa.ki-c.pro)
```bash
# DNS A tessa.ki-c.pro -> host, ports 80/443 open, .env reviewed
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
bash infra/scripts/issue-cert.sh   # Let's Encrypt
```

## Build phases
1. Foundation (Docker, Postgres, Nginx/TLS, TOTP auth) ✅
2. Agent core (workspace loader, orchestrator, LiteLLM chat) ✅
3. Vector system (Qdrant ingestion + retrieval) ✅
4. SwissChat connector (Bot Protocol v1) ✅
5. Tool & approval engine ✅
6. Admin autonomy (provider keys, agent autonomy) ✅
7. Hardening & extension (multi-workspace, hybrid RAG, monitoring,
   backups, CI) ✅

See `TESSA_SYSTEM_ARCHITECTURE.md` and `docs/` for full design.

## Make targets
`make up` · `make down` · `make logs` · `make ps` · `make test` · `make prod`
