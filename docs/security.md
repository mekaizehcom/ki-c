# Security (§29)

## Principles
- No provider keys in the frontend. Keys live in `.env` or are stored
  Fernet-encrypted in Postgres (set via Admin UI, Phase 6).
- Internal services (postgres, qdrant, redis, litellm, api, web) are not
  published in production — only nginx exposes 80/443.
- All admin / risky actions are audited (`audit_logs`).
- Risky actions require approval (Approval Engine, Phase 5).
- TOTP (RFC-6238) mandatory; enrolled on first login.
- Sessions are server-side and revocable (`sessions` table).
- Login rate-limit + account lockout after repeated failures.
- Backups encrypted (Phase 7). Vector access filtered by visibility.
- No free shell: command registry + templates + risk classification
  + execution sandbox + audit (Phase 5).

## Secrets
v1 uses `.env` (gitignored). `FERNET_KEY` encrypts provider keys and TOTP
secrets at rest. Architecturally ready for Docker secrets / Vault later.

## TLS
Let's Encrypt via certbot (webroot) for `tessa.ki-c.pro`; self-signed
fallback for local so the stack always boots.

## §33 Acceptance criteria — status
- [x] `https://tessa.ki-c.pro` reachable (nginx + self-signed; Let's
      Encrypt once DNS/SG ready)
- [x] Username + password + TOTP login
- [x] Web-UI chat works (REST + streaming WS)
- [x] ≥2 model profiles usable (default-fast/balanced/strong-reasoning,
      mock fallback without keys)
- [x] Workspace files loaded; SOUL/AGENTS/TOOLS/POLICIES effective
- [x] Documents uploaded and vectorized
- [x] Vector search used in answers (cited sources, hybrid rerank)
- [x] SwissChat messages processed (Bot Protocol v1)
- [x] Tool calls audited
- [x] Risky actions require approval (risk tiers + TOTP reconfirm)
- [x] Admins configure agent rights (autonomy + allowed_auto_actions)
- [x] No internal services public (only nginx 80/443 in prod overlay)

## §29 security pass
- Provider keys: never in frontend; Fernet-encrypted in Postgres or .env.
- Internal services unpublished in `docker-compose.prod.yml`.
- All admin/risky actions audited; TOTP reconfirm for high/critical.
- No free shell — fixed-argv registry, regex-validated targets, sandbox.
- Sessions server-side & revocable; login lockout + rate limit.
- Backups: `infra/scripts/backup.sh` (AES-256, pbkdf2).
- Monitoring: `/api/health`, `/health/ready`, `/health/metrics`;
  container healthchecks for api/web/worker/postgres/redis.
- Known v1 limitation: host-level commands (systemctl/docker/nginx on
  the host) need a constrained host-exec backend; the engine/approval/
  audit pipeline is complete and host-exec plugs in without API changes.
