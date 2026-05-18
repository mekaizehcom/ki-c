# Tessa — Active Context

> Diese Datei ist die wichtigste in einer neuen Session. Hier steht,
> **wo wir gerade stehen**. Bitte bei jeder substantiellen Änderung am
> System aktualisieren.

_Stand: 2026-05-18_

## Wo wir gerade sind

Tessa läuft in **Produktion auf `https://tessa.ki-c.pro`** mit gültigem
Let's-Encrypt-Zertifikat. Alle 7 Spec-Phasen (§32) sind implementiert,
getestet und gepusht. SwissChat-Bot ist gepaart und schickt erfolgreich
Nachrichten zurück (outbound geprüft).

Die noch laufende Aufgabe für den Endnutzer ist die **User-Verlinkung**:
- Nutzer sendet Nachricht an den `tessa`-Bot in SwissChat
- Bot antwortet mit einem 6-stelligen Linking-Code
- Nutzer trägt Code + TOTP auf `https://tessa.ki-c.pro/settings` ein
- Danach läuft jede SwissChat-Nachricht durch die Agent-Pipeline

## Letzte Entscheidungen (jüngste zuerst)

1. **Deterministische Slash-Commands im Chat** (Migration 0003).
   `_try_command()` läuft VOR jedem Modell-Aufruf in REST und WS:
   - `/help` — Liste aller Commands.
   - `/models` — verfügbare Modelle (gefiltert nach konfigurierten
     Providern, inkl. local-* wenn `MODEL_NODE_*_URL` gesetzt, plus
     `mock-echo`).
   - `/models <name>` — schreibt `conversations.model_override`.
     Wirkt sofort, persistent für die Conversation. `/models reset`
     löscht den Override.
   - `/agent <name>` / `/agent reset` — Agent-Switch in laufendem Chat.
   - `/status` — Host (Uptime, RAM, Disk), Tessa (queue depth,
     worker heartbeat, counts), aktuelle Conversation (Agent, Modell,
     Messages, geschätzte Token-Auslastung des Context-Windows),
     Provider-Status.
   - Unbekannte Slashes (z. B. `/path/to/file`) fallen weiter durch
     ans Modell — das ist Absicht, damit Code-Konversationen nicht
     gekapert werden.
2. **Agent kann seine eigenen Steering-Dateien selbst editieren.** Die
   `workspaces/`-Mount ist jetzt RW, zwei neue *internal* Tools
   (`workspace_read` / `workspace_write`) laufen in-process durch
   dieselbe Permission/Audit-Pipeline wie die argv-Tools. Chat-Path
   hat jetzt eine **Tool-Use-Schleife** (OpenAI/Anthropic function
   calling via LiteLLM, bis zu 5 Iterationen pro Turn).
   - `main`, `tessa-admin`, `document-agent` haben `Tools: workspace`,
     `Autonomie: scoped_auto`, whitelist `[workspace_read, workspace_write]`.
   - `workspace_write` ist `approval_required=False` — SOUL.md sagt
     "yours to evolve". Audit erfasst die unified diff bei jedem Write.
   - AGENTS.md-Parser liest jetzt zusätzlich `Erlaubte autonome Aktionen:`.
   - **End-to-end verifiziert:** gpt-4.1 hat im Chat `workspace_write`
     aufgerufen, MEMORY.md erweitert, Diff im Audit gelandet; danach
     manuell zurückgesetzt.
   - Caveat: Tool-Use läuft nur im REST-`/api/chat`-Pfad. Die WS-
     Streaming-Route bleibt text-only. Wenn die Web-UI Tools nutzen
     soll, ggf. für tool-fähige Agents auf REST umstellen.
2. **Memory Bank im Cline-Stil angelegt** — `memory-bank/` mit 6
   strukturierten Markdown-Dateien plus `AGENT_BOOTSTRAP.md`.
3. **SwissChat-Outbound geht über `POST /api/v1/bots/messages`,
   nicht `/api/v1/messages`.** Die öffentliche Bot-Protocol-Doku
   verschweigt das, der Live-Server erzwingt aber `sealed envelope`
   (ADR-021) auf `/messages`. Bots haben einen Ausnahme-Pfad
   (`/bots/messages`, ADR-042). Auth: weiter `service_token` als
   Bearer, kein JWT-Exchange für Senden nötig.
   → `app/channels/swisschat.py:send_message`
   → Commit `d52baef`
2. **TOTP-Enrollment zeigt jetzt zusätzlich das Base32-Secret** (4er-
   Gruppen, Copy-Button) — manuelle Eingabe als Fallback zur QR.
   → `app/routers/auth.py` returnt `enroll_secret`
   → `routes/login/+page.svelte`
   → Commit `adac2e2`
3. **Admin-Panel hat jetzt einen "SwissChat"-Bereich** mit
   Pair/Forget-Buttons (superadmin) und Status. Vorher gab es nur die
   API-Endpoints, die UI fehlte — das war Auslöser für die manuelle
   Pairing-Aktion.
   → `routes/admin/+page.svelte`
   → Commit `de35d98`
4. **`kai`-Superadmin TOTP wurde einmal zurückgesetzt** (DB-Delete
   auf `totp_secrets` + `users.totp_enabled=false`), weil die Test-
   Enrollments während Phase-1-Verifikation für den Echtnutzer eine
   "kein-QR"-Situation erzeugt hatten.

## Was als nächstes zu tun ist

In aufsteigender Wichtigkeit:

1. **Nutzer-Verlinkung abschließen** (siehe oben). Bis das passiert,
   ist SwissChat-Chat-Pipeline nicht erlebbar.
2. **Mock-Modell durch echte Provider ersetzen** — der Nutzer sagt, die
   Keys sind im Admin-Panel gesetzt (verifizieren mit
   `GET /api/admin/system` → `providers_active`). Wenn dort `false`
   steht: Provider per Admin-UI auf "enabled" setzen UND einen
   gültigen Key hochladen, dann nochmal prüfen.
3. **Backup-Schedule.** Backup-Skript existiert, ist aber nicht
   automatisiert. Vorschlag: systemd-timer `daily` + Offsite-Upload.
4. **Host-Exec für `devops`-Agent.** Phase-5-Pipeline ist komplett,
   aber `systemctl/docker/nginx`-Befehle auf dem Host funktionieren
   aus dem API-Container heraus nicht. Bewusste v1-Limitation
   (`docs/security.md` letzter Absatz). Plan: SSH-Worker
   `tessa-host-exec.service` mit Whitelist.
5. **Multi-Workspace UI.** Backend ist multi-workspace-fähig
   (`list_workspace_slugs()`), die Web-UI hat aber noch keine
   Workspace-Auswahl. Nicht dringend, bis ein zweiter Workspace
   gebraucht wird.

## Offene Fragen / aktuelle Unsicherheiten

- **SwissChat-Doku-Drift.** Die `bot-protocol/README.md` im swisschat-
  Repo ist an mehreren Stellen ungenau (Endpoint, Token-Typ). Wir
  sollten gelegentlich `git pull /tmp/swisschat` + Review machen,
  bevor wir uns auf die Doku verlassen. Quelle der Wahrheit ist der
  Code in `swisschat/api/src/routes/bots.ts`.
- **DeepSeek-Modell-Namen** im LiteLLM-Profil (`deepseek-reasoner` etc.)
  haben sich noch nicht in Production-Calls gespiegelt — beim ersten
  echten Aufruf bestätigen.

## Wichtige Anker (für eine neue Session)

- **URL:** `https://tessa.ki-c.pro` (Web-UI), `/api/*` für die API,
  `/webhook/swisschat` für inbound
- **Bootstrap-Superadmin:** `kai` (Passwort in `.env`
  `BOOTSTRAP_ADMIN_PASSWORD`). TOTP wurde vom Nutzer selbst enrolled.
- **Repo:** `git@github.com:mekaizehcom/ki-c.git`, Branch `main`,
  SSH-Deploy-Key in `~/.ssh/tessa_deploy`.
- **Letzter Commit:** `d52baef "SwissChat: send via /api/v1/bots/messages"`
- **Compose-Files für Prod:**
  `docker compose -f docker-compose.yml -f docker-compose.prod.yml ...`

## Routinen, die NICHT vergessen werden sollten

- **Vor `git commit`:** keine Sekrete versehentlich staged?
  `git status --porcelain | grep -E '(^|/)\.env$'` muss leer sein.
- **Nach Schema-Änderung:** neue Alembic-Revision in
  `services/api/migrations/versions/`, Entrypoint führt `upgrade head`
  automatisch beim API-Start.
- **Nach Code-Änderung in API/Web:** Im Prod-Overlay neu bauen:
  `docker compose -f ... -f docker-compose.prod.yml up -d --no-deps
  --build tessa-api tessa-web`. Im Dev-Overlay läuft API-Reload
  automatisch (uvicorn `--reload`), Web auch (Vite).
- **Nach Memory-Bank-relevanter Änderung:** `activeContext.md` +
  `progress.md` updaten. Das ist der Sinn der Bank.
