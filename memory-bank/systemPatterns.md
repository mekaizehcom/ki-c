# Tessa — System Patterns

> Wie die Stücke zusammenhängen. Kein Wiederkäuen der Spec — nur was
> für die Arbeit am Code relevant ist.

## High-level Datenfluss

```
Benutzer
  │  Web-UI (SvelteKit)   SwissChat (Bot)
  ▼                            ▼
  Nginx 80/443 (TLS terminator, einziges öffentliches Tor)
  │
  ├─ /                  → tessa-web   (SvelteKit, Node-Adapter)
  ├─ /api/*             → tessa-api   (FastAPI)
  ├─ /ws/chat           → tessa-api   (WebSocket, Upgrade)
  └─ /webhook/swisschat → tessa-api   (HMAC-signiert)

tessa-api  ─┬─►  postgres   (relationale Daten, §23-Schema)
            ├─►  qdrant     (Vektor-Suche)
            ├─►  redis      (Ingest-Queue, Idempotenz, Cache)
            ├─►  litellm    (Modell-Gateway, OpenAI/Anthropic/DeepSeek)
            └─►  swisschat  (https://swisschat.konnektai.pro, ausgehend)

tessa-worker ─►  brpop tessa:ingest in redis  → extract/chunk/embed
              ─►  qdrant (upsert) + postgres (document_chunks, vector_sources)
```

## OpenClaw-Workspace-Muster

Jeder Workspace liegt unter `workspaces/<slug>/` und enthält 9
steuernde Markdown-Dateien plus `config/workspace.yaml` und ein
`skills/`-Verzeichnis. Beim Start parst der **Workspace-Loader**
(`services/api/app/workspace.py`) diese Dateien und **synct** Agents +
Model-Profile in Postgres — sodass Admins später per UI ändern können,
ohne Markdown-Dateien zu editieren.

Wichtig: bei Konflikt zwischen `AGENTS.md` und DB-Zeile gewinnt die
**DB** (DB ist Wahrheit für Laufzeit). `clear_cache()` + Container-
Restart re-synct aus Markdown.

`list_workspace_slugs()` scannt das Verzeichnis und entdeckt
automatisch neue Workspaces (Multi-Workspace fähig).

## Tool Permission Engine (§20)

Vor JEDER Tool-Ausführung läuft `app/tools/engine.py:decide()` durch
diese Pipeline:

```
1. Kommando in Registry?               (app/tools/registry.py)
2. Rolle des Users ≥ AGENT_MIN_ROLE?
3. Agent darf dieses Tool?             (DB: agents.tools)
4. Risiko klassifizieren (low/medium/high/critical)
5. Autonomy-Level des Agenten:
     none            → DENY
     propose         → return "proposed" (zeigt argv, führt nicht aus)
     approve_required → Approval-Eintrag erstellen
     scoped_auto     → wenn cmd in agents.allowed_auto_actions: jetzt
                       ausführen (außer critical → trotzdem Approval)
     full_auto       → jetzt ausführen (außer critical)
6. Approval mit Approver-Rolle + ggf. TOTP-Reconfirm anlegen
```

`critical` braucht IMMER explizite Approval — auch unter `full_auto`.
Das ist ein hartcodierter Sicherheitsgürtel.

## Approval Engine (§18)

`app/approvals.py:finalize_approval()` ist die einzige Stelle, an der
ein pending Approval ausgeführt wird. Sie:

1. prüft Approver-Rolle ≥ APPROVER_ROLE[risk]
2. bei `risk ∈ {high, critical}` → TOTP-Reconfirm zwingend
3. baut `argv` aus Registry + gespeichertem Target neu (nie wiederverwenden)
4. ruft `tools/executor.py:run()` → Subprocess mit Timeout, `shell=False`
5. schreibt Audit + setzt `approvals.status = executed | executed_error | denied`

Approvals werden über Web-UI **und** SwissChat (`/approve <id> <totp>`)
finalisiert — identische Logik, kein zweites Codepfad.

## RAG-Pipeline

```
Upload  → app/routers/documents.py:upload  →  Redis enqueue
                                                 │
                                                 ▼
                  tessa-worker brpop  →  pipeline.py:ingest()
                                              │
                                              ├─ extract  (.md/.txt/.pdf/.docx/
                                              │           .html/.csv/.json/.log/.eml)
                                              ├─ chunk    (~600 Wörter, 90 Overlap)
                                              ├─ embed    (deterministic mock ODER
                                              │           OpenAI via LiteLLM)
                                              ├─ qdrant.upsert
                                              └─ postgres: document_chunks
                                                          + vector_sources
                                                          documents.status='ingested'

Retrieval (in Chat):
  app/routers/chat.py:_retrieval
    → vectors.search() mit role/user-Visibility-Filter
    → vectors.hybrid_rerank(0.6 vector + 0.4 lexical-overlap)
    → top-5 als zusätzlicher system-message in den LLM-Aufruf
    → Quellen kommen als `sources: [{n, filename, score}]` zurück
```

**Kritischer Invariant:** die Embedding-Funktion in
`services/api/app/vectors.py:embed_text` und
`services/worker/worker/pipeline.py:embed_text` MÜSSEN bit-identisch
sein. Sonst sieht der Query-Embedder andere Vektoren als die im Store.

## Modell-Routing-Muster

Profil (aus `MODELS.md`) → `provider/model` Tokens → `resolve_models()`
mapped auf LiteLLM-`model_name` aus `infra/litellm/config.yaml`,
filtert nach **Verfügbarkeit** des Provider-Keys (DB > .env > mock).
Letztes Element der Liste ist immer `mock-echo` (existiert ohne Key,
verhindert Totalausfall).

`provider_credentials(db, model)` liefert `{api_key, api_base}` für
den nächsten Call — pro Request an LiteLLM mitgegeben (dort
`allow_client_side_credentials: true`). Vorteil: API-Keys über das
Admin-Panel setzbar **ohne Gateway-Restart**.

## SwissChat-Connector (Bot Protocol v1, real-world)

Wichtige Realitäts­abweichungen vom offiziellen Bot-Protocol-Doc
(`docs/bot-protocol/README.md` des swisschat-Repos):

| Doc sagt | Tatsächlich |
|---|---|
| `POST /api/v1/messages` mit `{conversation_id, kind, plaintext}` + `Bearer service_token` | **`POST /api/v1/bots/messages`** mit gleichem Body + `Bearer service_token` |
| WS-Token-Exchange (§6) ist „nur für WS optional" | WS-Token-Exchange wird auch für `/api/v1/messages` gebraucht (sealed-envelope-Pflicht ADR-021). Für Bots gibt es aber den ADR-042-Sonderpfad `/bots/messages`, der diesen Exchange umgeht. |

Wir nutzen den Bot-Sonderpfad in `app/channels/swisschat.py:send_message`.
Der WS-Token-Exchange (`get_access_token`) bleibt für eventuelles
WS-Subscribe später erhalten, wird aber zum Senden nicht verwendet.

Webhook-Eingang läuft asynchron (`BackgroundTasks`), antwortet **<10s**
mit 200. Idempotenz via Redis-Key `swisschat:seen:{message_id}` (TTL 1h).
**Wichtig:** Exceptions in BackgroundTasks werden von FastAPI
*verschluckt*. `_process()` wrappt deshalb mit `try/except + print
traceback` — niemals naked lassen.

## Sicherheits-Invarianten

- **Keine Free-Shell.** Tools-Registry ist die einzige Stelle, an der
  Subprocesse gestartet werden. Targets via Regex validiert
  (`arg_pattern`), niemals `shell=True`.
- **Kein Plaintext-Secret in Code/UI.** Provider-API-Keys liegen
  Fernet-verschlüsselt in `model_providers.api_key_encrypted`. TOTP-
  Secrets ebenso in `totp_secrets.secret`. Bot-Service-Token in
  `integration_credentials.data_encrypted`.
- **Sessions sind serverseitig revokierbar.** Cookie enthält nur
  einen Random-Token; der `sha256(token)` ist der DB-Lookup-Key. Logout
  setzt `revoked=true`.
- **Production-Isolation.** Im Prod-Overlay sind nur `nginx` 80/443
  öffentlich. `postgres/redis/qdrant/litellm/api/web/worker` sind
  ausschließlich im `tessa-internal` Bridge-Netzwerk.

## Schichten-Karte (welche Datei wofür)

```
services/api/app/
├── config.py             pydantic-settings, .env-Mapping
├── db.py                 SQLAlchemy engine + SessionLocal
├── models.py             ORM-Tabellen (§23-Schema + Phase-Adds)
├── security.py           Argon2, Fernet, TOTP, Session-Tokens
├── schemas.py            Pydantic-Request/Response-Modelle
├── deps.py               get_current_user, require_role
├── audit.py              audit(db, action=..., risk_level=...)
├── workspace.py          Steering-File-Parser + DB-Sync
├── llm.py                LiteLLM-Client, model-router, fallback
├── vectors.py            Embeddings, Qdrant-Search, Hybrid-Rerank
├── queue.py              Redis-Queue + seen_once (Idempotenz)
├── integrations.py       Encrypted credential store
├── approvals.py          Approval-Engine (create + finalize)
├── seed.py               Bootstrap-Rollen + Superadmin
├── main.py               FastAPI app, lifespan, router-Wireup
├── channels/swisschat.py SwissChat Bot Protocol v1 client
├── tools/registry.py     Erlaubte Kommandos (argv + risk)
├── tools/engine.py       Permission-Decision-Pipeline
├── tools/executor.py     subprocess.run, timeout, sandbox
└── routers/
    ├── auth.py           login/totp/verify/qr/logout
    ├── me.py             /api/me
    ├── health.py         /api/health, /ready, /metrics
    ├── chat.py           Chat REST + WS + retrieval injection
    ├── documents.py      Upload, list, re-vectorize
    ├── tools.py          Tools list + execute + approvals
    ├── admin.py          Users, providers, agents, system
    └── swisschat.py      Webhook, pair, link, /commands
```
