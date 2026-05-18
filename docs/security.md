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
