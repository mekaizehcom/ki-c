# Tessa — Progress

> Was läuft, was nicht, was als nächstes. Quasi-Datenbank-View über die
> bereits geschaffte Arbeit.

_Stand: 2026-05-18_

## Phasen-Status

Alle 7 Spec-Phasen (§32) abgeschlossen, plus eine Produktions-Deployment-
Phase. 23 Unit-Tests laufen grün.

| Phase | Stand | Wesentliche Artefakte | Commit |
|---|---|---|---|
| 1 — Foundation | ✅ | Docker-Stack, Postgres §23-Schema, Nginx/TLS, Auth+TOTP | `b5cec3a` |
| 2 — Agent Core | ✅ | Workspace-Loader, LiteLLM-Router, Chat REST+WS | `a04fa72` |
| 3 — Vector | ✅ | Qdrant-Ingest, RAG mit Zitat | `332dbb8` |
| 4 — SwissChat | ✅ | Bot Protocol v1, Pair, Linking, Commands | `66d9b40` |
| 5 — Tools/Approval | ✅ | Permission-Engine, risikobasiertes Approval | `3686dfc` |
| 6 — Admin Autonomy | ✅ | Provider-Keys, Autonomy-Editor, User-Mgmt | `7818c98` |
| 7 — Hardening | ✅ | Multi-WS, Hybrid-RAG, Healthchecks, Backup, CI | `f2fd7d5` |
| Prod-Deploy | ✅ | Prod-Overlay live, Let's-Encrypt-Cert | `adac2e2`+ |
| SwissChat-Fix | ✅ | `/bots/messages`-Endpoint statt `/messages` | `d52baef` |
| Memory Bank | ✅ | Cline-Stil, 6 Dateien + AGENT_BOOTSTRAP | `27ccce1` |
| SOUL-Rewrite | ✅ | User-authored, opinionated identity | `098f75a` |
| Agent Self-Edit | ✅ | `workspace_*` internal tools + chat tool-use loop | `a020acd` |
| Slash-Commands | ✅ | `/help /status /models /agent` (REST + WS), Migration 0003 | `9115611` |
| Sandbox SSH | ✅ | `ssh_exec` remote_shell tool, Admin-UI für Host-Config, TOFU-Verifikation | `e32e06d` |
| Multi-Host SSH | ✅ | Tabelle `ssh_hosts`, gelabelte Targets, Migration 0004, Admin-Liste mit per-Host Test/Forget | (folgt) |

## Was nachweislich funktioniert (E2E geprüft)

- **Login-Flow:** Passwort + TOTP-Enrollment (QR **und** Klartext-Secret)
  + Session-Cookie.
- **Account-Lockout** nach `LOGIN_MAX_ATTEMPTS` (default 5),
  Auto-Unlock nach `LOGIN_LOCKOUT_MINUTES`.
- **Chat REST + WS-Streaming.** Streaming kommt durch Nginx-Upgrade-Map.
- **Modell-Fallback:** wenn kein Provider-Key konfiguriert → `mock-echo`
  antwortet sinnvoll, kein Crash.
- **Vektor-Pipeline:** Upload → Worker zieht aus Redis → Extract/Chunk/
  Embed/Upsert → Status `ingested` → semantische Suche liefert
  Treffer mit Score, in Chat-Antwort als `sources` zitiert.
- **Hybrid-Rerank** (0.6 vector + 0.4 lexical) — siehe Unit-Test
  `test_phase7.py:test_lexical_overlap_promotes_relevant_chunk`.
- **Tool-Aufrufe** mit Risiko-Tiering: low/medium/high/critical,
  Argv-Whitelist, Regex-Targets, Subprocess-Sandbox mit Timeout 30s.
- **Approval-Flow** mit TOTP-Reconfirm für high/critical (verifiziert,
  dass falscher TOTP-Code in 401 resultiert).
- **SwissChat:** Webhook akzeptiert nur HMAC-signierte POSTs (401 auf
  fake-sig), Outbound landet nachweisbar im SwissChat-UI.
- **TLS:** Echtes Let's-Encrypt-Zertifikat (Issuer E7), HSTS, gültig bis
  2026-08-16, Auto-Renewal-Loop läuft.
- **Prod-Isolation:** `ss -tlnp` zeigt nur 80/443 öffentlich; api/web/db
  nicht auf Host gemappt.
- **CI:** `.github/workflows/ci.yml` baut + testet bei jedem Push.

## Container-Inventur (auf der Live-Maschine)

```
tessa-api        prod build, healthy
tessa-web        prod build, healthy
tessa-worker     prod build, healthy
tessa-litellm    ghcr.io/berriai/litellm:main-latest
tessa-postgres   16, healthy, Volume `tessa_postgres_data`
tessa-qdrant     latest, Volume `tessa_qdrant_data`
tessa-redis      7, healthy
tessa-nginx      latest, Mount `infra/nginx/prod.conf` + LE-Volume
tessa-certbot    Renewal-Loop, Volumes `letsencrypt`, `certbot_www`
```

## Bekannte Lücken / Anti-Features

| Thema | Stand | Mitigation |
|---|---|---|
| Host-Exec für `devops`-Agent | Pipeline da, Execution leitet nicht auf Host weiter | Bewusste v1-Limit, dokumentiert. Plan in `activeContext.md`. |
| Automatisierter Backup | Skript da, kein Cron/Timer | Manuell ausführen. |
| Multi-Workspace UI | Backend ja, UI nein | Bei Bedarf eine Auswahl im Sidebar des Chats hinzufügen. |
| Externe Modell-Nodes (Ollama/vLLM) | LiteLLM-Profil konfiguriert, kein Node verbunden | URL in `.env`, Node bereitstellen. |
| OCR / Audio / Excel-Ingestion | Nicht in §27.2; Phase-7-Out-of-Scope | bei Bedarf nachrüsten. |
| Pydantic-V2-Migration | Größtenteils erledigt | Wenn Warnings aufschlagen, `class Config` → `ConfigDict`. |
| LiteLLM-Doku-Drift (mock_response auf openai/gpt-3.5-turbo) | Funktioniert | Bei LiteLLM-Upgrades verifizieren. |
| SwissChat-Doku-Drift | Wir nutzen Code als Quelle, nicht README | Bei nächstem Schema-Bruch wieder Code lesen. |

## Tests

Lauf: `services/api/tests/test_*.py`, 23 grün, 0 rot.

```
test_security.py      Passwort-Hash, Fernet-Roundtrip, TOTP
test_workspace.py     Steering-File-Parser
test_vectors.py       Embedding-Determinismus, Visibility-Mapping
test_swisschat.py     HMAC-Signatur-Verifizierung
test_tools.py         Argv-Injection-Schutz, Risiko-Klassen
test_admin.py         Provider-Credential-Resolution, Admin-Konstanten
test_phase7.py        Hybrid-Rerank, Workspace-Discovery
```

CI führt die Tests bei jedem Push aus. Lokal:

```bash
sudo docker run --rm -v $PWD/services/api:/srv -w /srv python:3.12-slim \
  sh -c "pip install -q -r requirements.txt && python -m pytest -q -p no:warnings"
```

## Migrations-Log

| Revision | Beschreibung |
|---|---|
| `0001_initial` | Komplettes §23-Schema (alle Tabellen) via `Base.metadata.create_all` |
| `0002_swisschat` | `integration_credentials` Tabelle + `conversations.external_id` Spalte/Index |

## Hot-Spots, wenn etwas nicht tut

| Symptom | Erste Anlaufstelle |
|---|---|
| Login klappt nicht / TOTP "wrong" | `audit_logs` filtern auf `login.%`. TOTP-Drift? Server-Uhr `date`. |
| Webhook 200, aber keine Reaktion | `tessa-api`-Logs nach `[swisschat]` grep. BackgroundTask-Exceptions werden in `_process()` geloggt. |
| Chat antwortet immer mit `mock-echo` | `GET /api/admin/system → providers_active`. Provider enabled + Key gesetzt? |
| Vector-Antwort hat keine Quellen | `GET /api/admin/system → ingest_queue, documents`. Status `ingested` in DB? Embedding-Dim konsistent zwischen API + Worker? |
| Tool 403 "agent not granted" | `agents.tools` in DB. Bei AGENTS.md-Änderung Container restarten oder Workspace neu syncen. |
| TLS-Browser-Warnung | `infra/certs/` enthält das Self-Signed; im Prod-Overlay läuft Nginx aus `letsencrypt`-Volume. |

## Letzte Verifikationen

| Test | Wann | Ergebnis |
|---|---|---|
| `https://tessa.ki-c.pro/api/health` ohne `-k` | 2026-05-18 | 200, kein Zert-Warning |
| HTTP→HTTPS Redirect | 2026-05-18 | 301 |
| Tests grün | 2026-05-18 | 23/23 |
| Container healthy | 2026-05-18 | alle relevanten ✓ |
| SwissChat Outbound | 2026-05-18 | Nachricht erfolgreich an `eb01f46e-…` (Bot `tessa`) |
| SwissChat Webhook signed | 2026-05-18 | 401 ohne Sig, 200 mit gültiger Sig |
