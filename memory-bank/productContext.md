# Tessa — Product Context

> Warum es Tessa gibt, für wen, und wie sich das "gut" anfühlen muss.

## Problem

Verteilte KI-Nutzung im Unternehmen hat drei Schmerzpunkte:

1. **Wildwuchs.** Jeder benutzt sein eigenes ChatGPT/Claude/Gemini-Konto,
   Provider-Keys liegen in Persons­konten, kein zentrales Audit, keine
   Rechte­verwaltung.
2. **Toter Kontext.** Firmen­wissen (Dokumente, Architektur­entscheidungen,
   Verfahrens­anweisungen) wird nicht systematisch in KI-Antworten
   eingespeist — jede Frage startet von Null.
3. **Riskante Aktionen ohne Leitplanken.** Wenn KI tatsächlich
   Server-Aktionen ausführen soll (deployen, neu starten, Firewall
   ändern), braucht es Policies, Approval Gates und Audit — nicht nur
   einen Chat.

Tessa löst alle drei zentral.

## Benutzer / Rollen

Aus §7.3 der Spec, im Code in `services/api/app/deps.py:ROLE_RANK`:

| Rolle | Macht | Typische Nutzung |
|---|---|---|
| `superadmin` | Vollzugriff inkl. Provider-Keys, kritische Aktionen | Plattform-Owner (`kai`) |
| `admin` | Workspaces, Agenten, Tools, Benutzer | Tech-Lead, Ops |
| `developer` | Entwicklungs-Agenten, technische Tools, mittlere Freigaben | Senior Devs |
| `user` | Chat, Suche, Dokumente | Normale Mitarbeiter:innen |
| `restricted` | Eingeschränkter Zugang | Externe / Gäste |

Rollen werden im **Admin-Panel** (`/admin`) gepflegt — nicht in YAML, nicht
in Code. Superadmin darf andere Superadmins anlegen.

## Kanäle

Aus §8:

- **Web-UI** (`https://tessa.ki-c.pro/`) ist der primäre Bedienkanal:
  Login, Chat, Dokumente, Approvals, Tools, Admin.
- **SwissChat** ist der zweite Kanal — Tessa erscheint dort als Bot
  (`@tessa`). Nutzer:innen führen ihren SwissChat-Account einmalig mit
  ihrem Tessa-Account zusammen (6-stelliger Linking-Code +
  TOTP-Bestätigung). Danach werden alle SwissChat-Nachrichten an die
  Tessa-Agentenpipeline weitergereicht.

Beide Kanäle teilen sich das **Conversation-Modell**: eine Conversation
hat `channel ∈ {web, swisschat}` und optional `external_id`, damit
Kontext kanalübergreifend bleibt.

## UX-Prinzipien

In `workspaces/company-default/SOUL.md` als Charakter codiert:

> Du unterscheidest immer zwischen: 1. Analyse, 2. Vorschlag, 3. Ausführung.

Operativ heißt das:

- **Sicht vor Aktion.** Tools werden separat aufgerufen; ein Chat-Turn
  führt nie unbemerkt eine produktive Aktion aus.
- **Quellen­angabe.** Antworten mit Vektor-Kontext zeigen die Quellen
  (Dateiname, Score) inline.
- **Klare Risikostufen.** Wenn eine Aktion Approval braucht, sagt Tessa
  das vor Ausführung explizit (`status: pending_approval`).
- **Audit als Default.** Jede Aktion landet in `audit_logs`, einsehbar
  im Admin-Panel.

## Was eine "gute" Tessa-Antwort ausmacht

1. **Verankert in Firmen­wissen**, wenn relevant (Vektor-Treffer eingeblendet
   mit Quellen-IDs `[1] datei.md (score)`).
2. **Modell-bewusst** — wenn `mock-echo` antwortet, weiß der Nutzer,
   dass kein echter Provider verfügbar ist.
3. **Risiko-bewusst** — wenn der Nutzer eine produktive Aktion
   anstößt, beschreibt Tessa Risiko, Approver-Rolle und ob TOTP-Reconfirm
   nötig ist, *bevor* irgendetwas passiert.
4. **Idempotent in Effekten** — derselbe `client_message_id` zweimal
   geschickt: kein doppelter Effekt.

## Anti-Goals

- **Keine "Magie"-Aktionen.** Tessa darf nichts ausführen, was nicht in
  `app/tools/registry.py` als fixe `argv`-Form steht.
- **Keine Free-Shell.** Auch nicht für Admins. Wer eine neue Operation
  braucht, baut ein Tool — kein RCE-Endpunkt.
- **Kein KI-Modell-Training auf Firmen-Daten** (in v1).
- **Kein Plaintext in Logs / Push** für Endnutzer-Konversationen
  (SwissChat sealed messaging, ADR-019/042 — Tessa-Bot-Path ist die
  dokumentierte Ausnahme).
