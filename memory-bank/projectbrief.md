# Tessa — Project Brief

> Fundament. Alles andere baut hierauf auf. Wenn diese Datei und eine
> andere widersprechen, hat diese hier Vorrang.

## Was ist Tessa?

Tessa ist die **firmeninterne KI-Agenten-Plattform** der Firmenumgebung.
Sie ist *kein* einzelner Chatbot, sondern ein zentraler **Agent-Orchestrator**,
der zwischen Benutzern, Modellen, Tools, Datenquellen, Vektorwissen,
Serverfunktionen und externen Diensten vermittelt.

- Primäre Domain: **https://tessa.ki-c.pro**
- Zielsystem: Ubuntu (aktuell 26.04 LTS auf EC2)
- Konzeptionelle Vorlage: OpenClaw-artige Workspaces mit steuernden
  Markdown-Dateien (`SOUL.md`, `AGENTS.md`, `TOOLS.md`, `POLICIES.md`,
  `MEMORY.md`, `MODELS.md`, `ROUTING.md`, `VECTOR.md`, `APPROVALS.md`).

## Was Tessa leisten muss (v1)

- Erreichbar über **Web-UI** und über den **SwissChat-Kanal** als Bot.
- **Benutzername + Passwort + TOTP** Authentifizierung (RFC-6238).
- Mehrere KI-Modelle / Provider zentral verwalten
  (OpenAI, Anthropic, DeepSeek; lokale Model Nodes vorbereitet).
- **Vektor-Datenbank** für langfristige, semantische Wissensspeicherung.
- **Admin-konfigurierbare Autonomie** pro Agent
  (`none / propose / approve_required / scoped_auto / full_auto`).
- **Approval Gates** für riskante Aktionen, TOTP-Reconfirm für high/critical.
- **Vollständiges Audit** aller Aktionen, Entscheidungen, Freigaben.
- **Selbstverwaltung**: Tessa soll perspektivisch die eigene Instanz
  analysieren, warten und verwalten können — aber nur im vom Admin
  freigegebenen Rahmen.

## Was Tessa explizit NICHT leisten muss (v1)

- Vollständiges Unternehmens-SSO
- Direkte produktive Steuerung aller externen Dienste
- Komplexe Multi-Tenant-Abrechnung
- Perfekte Verarbeitung aller Dokumenttypen
- Vollautonome Serververwaltung ohne Admin-Konfiguration
- Eigene mobile App
- Eigenes KI-Modell trainieren

Architektonisch vorbereitet, aber nicht zwingend ausgeliefert.

## Erfolgsformel (Acceptance Criteria, §33 der Spec)

v1 gilt als funktionsfähig, wenn:

1. `https://tessa.ki-c.pro` erreichbar ist
2. Login mit Benutzername + Passwort + TOTP funktioniert
3. Web-UI-Chat funktioniert
4. ≥ 2 Modellprofile nutzbar sind
5. Workspace-Dateien geladen werden (SOUL/AGENTS/TOOLS/POLICIES wirksam)
6. Dokumente hochgeladen und vektorisiert werden können
7. Vektor-Suche in Antworten genutzt wird (mit Quellenangabe)
8. SwissChat-Nachrichten verarbeitet werden können
9. Tool-Aufrufe auditierbar sind
10. Riskante Aktionen Approval benötigen
11. Admins Agentenrechte konfigurieren können
12. Keine internen Services öffentlich erreichbar sind

Stand 2026-05-18: **alle 12 erfüllt** (siehe `progress.md` für Details).

## Quelldokumente

- `docs/architecture.md` (= `TESSA_SYSTEM_ARCHITECTURE.md`, Version 1.0)
  — eingefrorene Originalspezifikation in 36 Abschnitten.
- `README.md` — Quick start, Make-Targets.
- `docs/security.md` — §29 Sicherheitsprinzipien + §33-Checkliste.
- `docs/deployment.md` — Prod-Deployment.

## Eigentum / Kontext

- Repo: **github.com/mekaizehcom/ki-c** (Branch `main`)
- Server: tessa.ki-c.pro (54.76.15.82, EC2, Ubuntu 26.04 LTS, 2 vCPU, 7.6 GB RAM)
- Bootstrap-Admin: User `kai` (Superadmin, in `.env` als
  `BOOTSTRAP_ADMIN_*` definiert)
