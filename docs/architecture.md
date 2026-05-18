# TESSA – Konzeptdokument für eine firmeninterne KI-Agenten-Umgebung

**Projektname:** Tessa  
**Primäre Domain:** `tessa.ki-c.pro`  
**Zielsystem:** Ubuntu Server  
**Dokumenttyp:** Technisches Architektur- und Umsetzungskonzept  
**Zielgruppe:** Entwickler, DevOps, Systemarchitekten, technische Projektleitung  
**Version:** 1.0  
**Stand:** 18.05.2026  

---

## 1. Executive Summary

Tessa soll als firmeninterne KI-Agenten-Umgebung aufgebaut werden. Das System orientiert sich konzeptionell an OpenClaw-artigen Arbeitsumgebungen mit steuernden Workspace-Dateien wie `SOUL.md`, `AGENTS.md`, `TOOLS.md`, `POLICIES.md`, `MEMORY.md`, `MODELS.md` und `ROUTING.md`.

Tessa ist nicht als einzelner Chatbot zu verstehen, sondern als zentraler Agent-Orchestrator für die Firmenumgebung. Das System soll:

- über eine Web-UI erreichbar sein,
- zusätzlich über SwissChat als Chat-Kanal angebunden werden,
- mehrere KI-Modelle und Provider zentral verwalten,
- externe Modellinstanzen anbinden können,
- über eine Vektor-Datenbank langfristige, effiziente KI-Datenhaltung ermöglichen,
- administrative Aktionen an der eigenen Instanz durchführen können,
- je nach Admin-Konfiguration mit Approval-Gates oder vollautonom arbeiten,
- Benutzer per Benutzername und TOTP-Code aus einer Authenticator-App authentifizieren,
- Chat-, Dokumenten- und Systemdaten vektorisieren und für spätere KI-Nutzung verfügbar machen.

Die primäre Instanz läuft unter:

```text
https://tessa.ki-c.pro
```

---

## 2. Zielsetzung

### 2.1 Hauptziel

Aufbau einer zentralen, kontrollierbaren und erweiterbaren KI-Agenten-Plattform für die Firmenumgebung.

Tessa soll als internes KI-Betriebssystem fungieren, das zwischen Benutzern, Modellen, Tools, Datenquellen, Vektorwissen, Serverfunktionen und externen Diensten vermittelt.

### 2.2 Fachliche Ziele

Tessa soll:

- interne Benutzer über Web-UI und SwissChat bedienen,
- Aufgaben kontextbezogen an passende Agenten weiterleiten,
- unterschiedliche Modelle je nach Aufgabe verwenden,
- projektspezifische Regeln über Markdown-Dateien laden,
- langfristige Datenhaltung über Vektorindizes ermöglichen,
- Firmenwissen durchsuchbar und wiederverwendbar machen,
- Aktionen an Servern, Diensten, Dateien und Deployments kontrolliert ausführen,
- für jeden Agenten klare Rechte und Grenzen definieren,
- Admins die Steuerung über Autonomiegrad, Modelle, Tools und Sicherheitsregeln geben.

### 2.3 Technische Ziele

Technisch soll Tessa:

- auf Ubuntu laufen,
- containerisiert betrieben werden,
- über Nginx oder Caddy per HTTPS erreichbar sein,
- eine zentrale Authentifizierung mit Benutzername + TOTP bieten,
- eine relationale Datenbank für Benutzer, Konfiguration, Sessions und Audit-Logs nutzen,
- eine Vektor-Datenbank für KI-Wissen nutzen,
- einen Modell-Gateway für Multi-Provider-Nutzung verwenden,
- externe Modellknoten anbinden können,
- über eine API sowohl Web-UI als auch SwissChat bedienen,
- modular erweiterbar sein.

---

## 3. Nicht-Ziele der ersten Version

In der ersten Version muss Tessa noch nicht:

- ein vollständiges Unternehmens-SSO unterstützen,
- alle externen Dienste direkt produktiv steuern,
- komplexe Multi-Tenant-Abrechnung bieten,
- alle Dokumenttypen perfekt analysieren,
- vollständige autonome Serververwaltung ohne Admin-Konfiguration durchführen,
- eine mobile App bereitstellen,
- ein eigenes KI-Modell trainieren.

Diese Punkte sollen architektonisch vorbereitet, aber nicht zwingend in Version 1 vollständig umgesetzt werden.

---

## 4. Grundarchitektur

### 4.1 Architekturübersicht

```text
Benutzer
  ├── Web-UI
  └── SwissChat
        ↓
Tessa API Gateway
        ↓
Authentication Layer
        ↓
Agent Orchestrator
        ↓
Workspace / Steering Files
        ↓
Tool Permission Engine
        ↓
Model Router / LiteLLM Gateway
        ↓
KI-Modelle
  ├── OpenAI
  ├── Anthropic
  ├── Google Gemini
  ├── Mistral
  └── externe lokale Modellinstanzen

Parallel:
        ↓
Vector Memory Layer
        ↓
Vector DB + PostgreSQL
```

### 4.2 Hauptkomponenten

| Komponente | Zweck |
|---|---|
| Web-UI | Browserbasierte Bedienung von Tessa |
| SwissChat Connector | Chat-Anbindung über SwissChat |
| API Gateway | Einheitlicher Zugriffspunkt für UI, SwissChat und spätere APIs |
| Auth Service | Benutzername + TOTP Authentifizierung |
| Agent Orchestrator | Zentrale Steuerung der Agentenlogik |
| Workspace Loader | Lädt `SOUL.md`, `AGENTS.md`, `TOOLS.md`, Policies usw. |
| Model Router | Wählt passendes Modell je Aufgabe |
| LiteLLM Gateway | Einheitliche Provider-Schnittstelle |
| Tool Engine | Führt erlaubte Tools aus |
| Approval Engine | Erzwingt Freigaben bei riskanten Aktionen |
| Vector Memory | Vektorisiert Inhalte und stellt semantische Suche bereit |
| Audit Log | Protokolliert Aktionen, Entscheidungen und Freigaben |
| Admin Panel | Verwaltung von Benutzern, Modellen, Tools und Autonomiegrad |

---

## 5. Server-Topologie

### 5.1 Hauptserver

Der Hauptserver betreibt die Tessa-Kerninstanz.

```text
Server: Ubuntu
Domain: tessa.ki-c.pro
Funktion:
- Web-UI
- API
- Auth
- Agent Orchestrator
- LiteLLM Gateway
- PostgreSQL
- Vector DB
- Redis optional
- Nginx / Caddy
```

### 5.2 Separate Modellinstanzen

Ollama oder andere lokale Modellserver sollen ausdrücklich nicht auf dem Hauptserver laufen.

Stattdessen:

```text
Model Node 1
- Ollama / vLLM / LM Studio Server
- GPU oder CPU optimiert
- interne API
- nur aus Tessa-Netz erreichbar

Model Node 2 optional
- alternative Modelle
- Spezialmodelle
- größere GPU-Instanz
```

Beispiel:

```text
http://model-node-1.internal:11434
http://model-node-2.internal:8000
```

### 5.3 Netzwerkprinzip

```text
Internet
  ↓
tessa.ki-c.pro
  ↓
Nginx / Caddy
  ↓
Tessa API / Web UI
  ↓
interne Services
  ├── PostgreSQL
  ├── Vector DB
  ├── Redis
  ├── LiteLLM
  └── Model Nodes
```

Interne Dienste dürfen nicht öffentlich erreichbar sein.

---

## 6. Domain und TLS

### 6.1 Domain

Die primäre Domain lautet:

```text
tessa.ki-c.pro
```

### 6.2 HTTPS

Für die Domain muss ein TLS-Zertifikat eingerichtet werden.

Empfehlung:

```text
Let's Encrypt
Nginx oder Caddy
Auto-Renewal aktiv
HTTP → HTTPS Redirect
```

### 6.3 Subdomains optional

Später können getrennte Subdomains verwendet werden:

```text
api.tessa.ki-c.pro
admin.tessa.ki-c.pro
models.tessa.ki-c.pro
docs.tessa.ki-c.pro
```

Für Version 1 reicht jedoch:

```text
https://tessa.ki-c.pro
```

mit internem Routing.

---

## 7. Authentifizierung

### 7.1 Login-Verfahren

Benutzer melden sich mit:

```text
Benutzername
Passwort
TOTP-Code aus Google Authenticator oder kompatibler App
```

Der TOTP-Code soll nach RFC-6238 kompatibel sein.

### 7.2 Benutzerverwaltung

Benutzer werden initial durch Admins angelegt.

Benutzerobjekt:

```yaml
user:
  username: kai
  display_name: Kai
  role: admin
  totp_enabled: true
  status: active
  allowed_channels:
    - web
    - swisschat
```

### 7.3 Rollen

Empfohlene Rollen:

| Rolle | Beschreibung |
|---|---|
| Superadmin | Vollzugriff auf System, Modelle, Benutzer und Policies |
| Admin | Verwaltung von Workspaces, Agenten, Tools und Nutzern |
| Developer | Zugriff auf Entwicklungsagenten und technische Tools |
| User | Normale Nutzung von Chat, Suche und Dokumenten |
| Restricted | Eingeschränkter Zugang zu definierten Agenten |

### 7.4 Session-Sicherheit

- Sessions mit Ablaufzeit
- Refresh-Token serverseitig widerrufbar
- TOTP bei Login verpflichtend
- Admin-Aktionen optional mit erneutem TOTP bestätigen
- Rate-Limit für Login-Versuche
- Account Lockout nach mehreren Fehlversuchen

---

## 8. Zugriffskanäle

### 8.1 Web-UI

Die Web-UI ist der primäre Bedienkanal.

Funktionen:

- Login
- Chat mit Agenten
- Auswahl von Workspace / Agent / Modellprofil
- Anzeige von Quellen und Vektor-Treffern
- Upload von Dokumenten
- Admin-Bereich
- Approval-Requests
- Audit-Ansicht
- Systemstatus

### 8.2 SwissChat Connector

SwissChat wird als Messenger-Kanal angebunden.

Architektur:

```text
SwissChat
  ↓
SwissChat Webhook / Bot API
  ↓
Tessa Channel Adapter
  ↓
Tessa Conversation API
  ↓
Agent Orchestrator
```

Der SwissChat Connector muss:

- eingehende Nachrichten empfangen,
- Benutzer anhand SwissChat-ID einem Tessa-User zuordnen,
- bei Bedarf TOTP-Verknüpfung durchführen,
- Antworten senden,
- Medien/Dokumente optional weiterreichen,
- Approval-Anfragen darstellen können.

### 8.3 Kanalübergreifende Sessions

Ein Benutzer kann sowohl über Web-UI als auch SwissChat arbeiten.

Daher braucht Tessa ein kanalübergreifendes Conversation-Modell:

```yaml
conversation:
  id: uuid
  user_id: uuid
  channel: web | swisschat
  workspace_id: uuid
  agent_id: devops
  created_at: timestamp
  status: active
```

---

## 9. OpenClaw-artiges Workspace-Konzept

### 9.1 Grundidee

Jeder Workspace enthält steuernde Dateien. Diese Dateien bestimmen, wie Tessa in diesem Kontext arbeitet.

Beispiel:

```text
/workspaces/company-default
├── SOUL.md
├── AGENTS.md
├── TOOLS.md
├── POLICIES.md
├── MEMORY.md
├── MODELS.md
├── ROUTING.md
├── VECTOR.md
├── APPROVALS.md
├── skills/
│   ├── ubuntu/
│   │   └── SKILL.md
│   ├── nginx/
│   │   └── SKILL.md
│   ├── docker/
│   │   └── SKILL.md
│   ├── postgres/
│   │   └── SKILL.md
│   └── swisschat/
│       └── SKILL.md
└── config/
    └── workspace.yaml
```

### 9.2 Zweck dieser Dateien

| Datei | Zweck |
|---|---|
| `SOUL.md` | Identität, Grundhaltung und Arbeitsweise |
| `AGENTS.md` | Definition der verfügbaren Agenten |
| `TOOLS.md` | Tool-Kategorien und Berechtigungen |
| `POLICIES.md` | Sicherheits- und Unternehmensregeln |
| `MEMORY.md` | explizites Projektgedächtnis |
| `MODELS.md` | verfügbare Modellprofile |
| `ROUTING.md` | Regeln für Modellauswahl |
| `VECTOR.md` | Regeln zur Vektorisierung und Datenhaltung |
| `APPROVALS.md` | Freigabeprozesse |
| `skills/` | modulare Fähigkeiten |
| `workspace.yaml` | maschinenlesbare Hauptkonfiguration |

---

## 10. `SOUL.md`

### 10.1 Zweck

`SOUL.md` definiert die Grundidentität von Tessa innerhalb eines Workspaces.

Beispiel:

```md
# SOUL.md

Du bist Tessa, der interne AI-Agent der Firmenumgebung.

Deine Arbeitsweise:
- präzise
- nachvollziehbar
- sicherheitsbewusst
- lösungsorientiert
- technisch exakt
- dokumentierend

Du unterscheidest immer zwischen:
1. Analyse
2. Vorschlag
3. Ausführung

Du führst produktive Aktionen nur aus, wenn:
- der Admin dies für den Agenten erlaubt hat,
- das Tool dafür freigegeben ist,
- keine Policy verletzt wird,
- ein eventuell erforderliches Approval vorliegt.

Du bist in der Lage, die eigene Instanz zu analysieren, zu warten und zu verwalten, sofern Deine Berechtigungen dies erlauben.
```

---

## 11. `AGENTS.md`

### 11.1 Zweck

`AGENTS.md` definiert die verfügbaren Agenten und ihre Rollen.

Beispiel:

```md
# AGENTS.md

## main
Zweck:
Allgemeiner Firmenassistent.

Modellprofil:
default-balanced

Tools:
- search_vector
- read_memory
- write_memory_proposal
- document_reader

Autonomie:
low

---

## devops
Zweck:
Verwaltung und Analyse der Ubuntu-Serverumgebung.

Modellprofil:
strong-reasoning

Tools:
- shell_readonly
- shell_write
- docker
- nginx
- systemd
- logs
- file_editor

Autonomie:
admin-configurable

Approval erforderlich für:
- Neustart von Diensten
- Änderungen an Nginx
- Änderungen an Firewall
- Paketinstallationen
- Löschen von Dateien
- Deployment
- Änderungen an Docker Compose

---

## tessa-admin
Zweck:
Verwaltung der Tessa-Instanz selbst.

Modellprofil:
strong-reasoning

Tools:
- tessa_config
- user_admin
- model_admin
- vector_admin
- audit_reader
- service_manager

Autonomie:
admin-configurable

---

## code-reviewer
Zweck:
Analyse von Code, Pull Requests und Architektur.

Modellprofil:
code-premium

Tools:
- repo_reader
- git_diff
- static_analysis
- search_vector

Autonomie:
medium

---

## document-agent
Zweck:
Dokumentenverarbeitung, Zusammenfassung, Vektorisierung und Wissensextraktion.

Modellprofil:
default-balanced

Tools:
- document_reader
- vector_write
- vector_search
- metadata_extractor

Autonomie:
medium
```

---

## 12. `TOOLS.md`

### 12.1 Zweck

`TOOLS.md` definiert, welche Aktionen Tessa ausführen darf.

Beispiel:

```md
# TOOLS.md

## shell_readonly

Erlaubt:
- pwd
- ls
- cat
- head
- tail
- grep
- find
- df
- du
- free
- uptime
- systemctl status
- journalctl
- docker ps
- docker logs
- nginx -t

Nicht erlaubt:
- Dateiänderungen
- Neustarts
- Paketinstallationen
- Löschen
- Rechteänderungen

---

## shell_write

Erlaubt nach Policy-Prüfung:
- Datei schreiben
- Konfiguration ändern
- systemctl restart
- docker compose up
- docker compose down
- apt install
- certbot
- nginx reload

Approval:
standardmäßig erforderlich

---

## vector_search

Erlaubt:
- semantische Suche
- Abruf von Kontext
- Retrieval für Antworten

---

## vector_write

Erlaubt:
- Dokumente vektorisieren
- Chatverläufe vektorisieren
- Memory-Einträge erzeugen
- Metadaten speichern

Approval:
nicht erforderlich, sofern Dokumentquelle erlaubt ist

---

## tessa_config

Erlaubt:
- Lesen der Tessa-Konfiguration
- Vorschläge für Änderungen
- Änderung nach Admin-Freigabe

---

## swisschat

Erlaubt:
- Nachrichten lesen
- Antworten senden
- Approval-Nachrichten senden
- Benutzerzuordnung prüfen

E-Mail-, Zahlungs- oder produktive externe Aktionen sind nicht Teil dieses Tools.
```

---

## 13. `POLICIES.md`

### 13.1 Zweck

`POLICIES.md` enthält Sicherheits- und Unternehmensregeln.

Beispiel:

```md
# POLICIES.md

## Grundregel

Tessa darf nur Aktionen ausführen, die:
- einem aktiven Benutzer zugeordnet sind,
- durch dessen Rolle erlaubt sind,
- durch den Agenten erlaubt sind,
- durch das Tool erlaubt sind,
- durch Workspace-Policies erlaubt sind.

## Produktive Aktionen

Produktive Aktionen benötigen standardmäßig Approval, außer ein Admin hat sie für einen Agenten ausdrücklich freigegeben.

## Immer Approval erforderlich

- Löschen von Dateien
- Änderungen an Firewall
- Änderungen an DNS
- Änderungen an TLS-Zertifikaten
- Änderungen an Nginx
- Docker Compose Down
- Datenbankmigrationen
- Benutzerrechte ändern
- Modellprovider-Keys ändern
- Vektorindex löschen
- Produktionsdeployment

## Optional autonom erlaubt

Ein Admin kann für definierte Bereiche Autonomie erlauben, z. B.:

- Log-Analyse
- Neustart nicht-kritischer Worker
- Vektorisierung neuer Dokumente
- Aktualisierung interner Memory-Einträge
- Cleanup temporärer Dateien
```

---

## 14. `MODELS.md`

### 14.1 Zweck

`MODELS.md` beschreibt Modellprofile unabhängig vom konkreten Provider.

Beispiel:

```md
# MODELS.md

## default-fast

Zweck:
Schnelle, einfache Aufgaben.

Beispiele:
- kurze Antworten
- Klassifikation
- einfache Umformulierungen

Provider:
- openai/gpt-4o-mini
- google/gemini-flash
- anthropic/claude-haiku

---

## default-balanced

Zweck:
Normale Firmenarbeit.

Beispiele:
- Zusammenfassungen
- E-Mails
- Dokumentanalyse
- SwissChat-Antworten
- allgemeine Assistenz

Provider:
- openai/gpt-4.1
- anthropic/claude-sonnet
- google/gemini-pro

---

## strong-reasoning

Zweck:
Komplexe Aufgaben.

Beispiele:
- Serveranalyse
- Architektur
- Deploymentplanung
- komplexe Fehleranalyse
- Sicherheitsbewertung

Provider:
- anthropic/claude-sonnet
- openai/gpt-5
- google/gemini-pro

---

## local-private

Zweck:
Sensible Daten und lokale Verarbeitung.

Endpoint:
- http://model-node-1.internal:11434
- http://model-node-2.internal:8000

Provider:
- ollama/qwen
- ollama/llama
- vllm/mistral
```

---

## 15. `ROUTING.md`

### 15.1 Zweck

`ROUTING.md` legt fest, wann welches Modellprofil verwendet wird.

Beispiel:

```md
# ROUTING.md

Nutze default-fast für:
- kurze SwissChat-Antworten
- einfache Zusammenfassungen
- Klassifikation
- Routing-Entscheidungen

Nutze default-balanced für:
- normale Web-UI Chats
- Dokumentenanalyse
- Antwortgenerierung mit Vektor-Kontext
- interne Assistenz

Nutze strong-reasoning für:
- DevOps
- Debugging
- Sicherheitsfragen
- Architekturentscheidungen
- komplexe mehrstufige Aufgaben

Nutze local-private für:
- vertrauliche Kundendaten
- interne Finanzdaten
- personenbezogene Inhalte
- nicht nach außen zu sendende Dokumente

Fallback:
Wenn ein Modell nicht erreichbar ist, verwende das nächstniedrigere erlaubte Profil.
```

---

## 16. `VECTOR.md`

### 16.1 Zweck

`VECTOR.md` definiert die Vektor-Datenhaltung.

Tessa soll Inhalte nicht nur speichern, sondern semantisch nutzbar machen.

### 16.2 Zu vektorisierende Inhalte

Folgende Inhalte sollen vektorisiert werden können:

- Chatverläufe
- SwissChat-Konversationen
- Web-UI-Konversationen
- hochgeladene Dokumente
- Markdown-Dateien
- technische Logs
- Projektwissen
- Memory-Einträge
- relevante Systemkonfigurationen
- Ergebnisse abgeschlossener Aufgaben
- interne Anleitungen
- Skill-Dokumentationen

### 16.3 Datenklassen

```yaml
vector_classes:
  conversation:
    retention: configurable
    default_visibility: user_private

  document:
    retention: persistent
    default_visibility: workspace

  system_knowledge:
    retention: persistent
    default_visibility: admin

  task_result:
    retention: persistent
    default_visibility: workspace

  memory:
    retention: persistent
    default_visibility: workspace
```

### 16.4 Sichtbarkeiten

```text
user_private
team
workspace
admin
global
```

### 16.5 Empfohlene Vektor-Datenbank

Für Version 1 werden zwei Optionen empfohlen:

#### Option A: Qdrant

Vorteile:

- sehr gut für dedizierte Vektor-Suche
- einfache Docker-Installation
- performante semantische Suche
- klare Collections
- gute API

#### Option B: PostgreSQL mit pgvector

Vorteile:

- weniger Infrastruktur
- direkt in PostgreSQL integriert
- gut für kleinere bis mittlere Datenmengen
- Backup einfacher

### 16.6 Empfehlung

Für Tessa wird empfohlen:

```text
PostgreSQL für relationale Daten
Qdrant für Vektor-Daten
```

Begründung:

- klare Trennung von Systemdaten und semantischem Speicher
- skalierbarer
- einfacher später auf eigene Vektor-Strategien erweiterbar

### 16.7 Vektor-Pipeline

```text
Quelle
  ↓
Ingestion
  ↓
Chunking
  ↓
Metadata Extraction
  ↓
Embedding Model
  ↓
Vector DB
  ↓
Retrieval
  ↓
Agent Context
```

### 16.8 Chunking-Regeln

Empfehlung:

```yaml
chunking:
  default_chunk_size_tokens: 800
  overlap_tokens: 120
  preserve_headings: true
  preserve_code_blocks: true
  preserve_tables: true
```

### 16.9 Metadaten

Jeder Vektor-Eintrag muss Metadaten enthalten:

```yaml
metadata:
  id: uuid
  source_type: document | chat | memory | log | config
  source_id: uuid
  workspace_id: uuid
  user_id: uuid optional
  visibility: user_private | team | workspace | admin | global
  created_at: timestamp
  updated_at: timestamp
  tags:
    - string
  checksum: string
```

---

## 17. `MEMORY.md`

### 17.1 Zweck

`MEMORY.md` enthält explizites, kuratiertes Workspace-Wissen.

Nicht jeder Chatverlauf ist automatisch Memory. Memory ist Wissen, das als relevant bestätigt oder durch Policy erlaubt wurde.

Beispiel:

```md
# MEMORY.md

## System

Die Hauptinstanz läuft unter:
https://tessa.ki-c.pro

## Architekturentscheidungen

- Ollama läuft nicht auf dem Hauptserver.
- Lokale Modelle laufen auf separaten Model Nodes.
- Benutzerlogin erfolgt über Benutzername + TOTP.
- Web-UI und SwissChat sind die primären Kanäle.
- Inhalte sollen vektorisiert werden.
- Tessa soll perspektivisch die eigene Instanz verwalten können.

## Sicherheitsprinzip

Admin bestimmt den Autonomiegrad pro Agent und Tool.
```

---

## 18. `APPROVALS.md`

### 18.1 Zweck

`APPROVALS.md` beschreibt Freigabeprozesse.

Beispiel:

```md
# APPROVALS.md

## Approval-Typen

### low-risk
Beispiele:
- Dokument vektorisieren
- Chat zusammenfassen
- Memory-Vorschlag erstellen

Freigabe:
nicht erforderlich

### medium-risk
Beispiele:
- Datei erstellen
- Konfigurationsvorschlag schreiben
- nicht-produktiven Dienst neustarten

Freigabe:
Admin oder Developer

### high-risk
Beispiele:
- Nginx ändern
- Docker Compose Down
- Firewall ändern
- Zertifikat ändern
- Datenbankmigration
- produktives Deployment

Freigabe:
Admin erforderlich
TOTP-Reconfirm empfohlen

### critical
Beispiele:
- Benutzerrechte ändern
- Provider-Keys ändern
- Vektorindex löschen
- produktive Daten löschen

Freigabe:
Superadmin erforderlich
TOTP-Reconfirm erforderlich
Audit zwingend
```

---

## 19. Admin-gesteuerte Autonomie

### 19.1 Ziel

Tessa soll langfristig die eigene Instanz verwalten können. Der Grad der Autonomie wird durch Admins bestimmt.

### 19.2 Autonomiestufen

```yaml
autonomy_levels:
  none:
    description: Nur Analyse, keine Aktionen

  propose:
    description: Aktionen werden vorgeschlagen, aber nicht ausgeführt

  approve_required:
    description: Aktionen werden nach Freigabe ausgeführt

  scoped_auto:
    description: Aktionen innerhalb definierter Grenzen automatisch erlaubt

  full_auto:
    description: Vollautomatische Ausführung innerhalb definierter Policies
```

### 19.3 Beispiel

```yaml
agents:
  devops:
    autonomy: approve_required

  tessa-admin:
    autonomy: scoped_auto
    allowed_auto_actions:
      - restart_worker
      - rotate_logs
      - reindex_failed_documents
```

---

## 20. Tool Permission Engine

### 20.1 Prüfung vor jeder Aktion

Vor jeder Tool-Ausführung müssen geprüft werden:

```text
User Role
Agent Role
Workspace Policy
Tool Policy
Autonomy Level
Approval Requirement
Target Resource
Risk Level
```

### 20.2 Entscheidungslogik

```text
Darf der Benutzer diesen Agenten verwenden?
Darf der Agent dieses Tool verwenden?
Ist das Tool für diese Ressource erlaubt?
Ist die Aktion riskant?
Liegt Approval vor?
Muss TOTP erneut abgefragt werden?
Aktion ausführen oder blockieren.
```

### 20.3 Beispiel

```yaml
request:
  user: kai
  role: admin
  agent: devops
  tool: nginx
  action: reload

decision:
  allowed: true
  approval_required: true
  reason: "nginx reload is a medium/high risk server action"
```

---

## 21. Multi-Model-Gateway

### 21.1 Zweck

Das Modell-Gateway kapselt alle Provider und stellt eine einheitliche Schnittstelle bereit.

Empfohlen:

```text
LiteLLM Proxy
```

### 21.2 Aufgaben

- Provider-Keys zentral verwalten
- Modelle abstrahieren
- Fallbacks ermöglichen
- Kosten erfassen
- Ratenlimits setzen
- Teams und Budgets verwalten
- lokale Model Nodes anbinden
- OpenAI-kompatible API bereitstellen

### 21.3 Provider

Initial vorgesehen:

```yaml
providers:
  - openai
  - anthropic
  - google
  - mistral
  - local_model_nodes
```

---

## 22. Vektor-gestütztes Retrieval

### 22.1 Antwortprozess mit Vektor-Kontext

```text
User Prompt
  ↓
Intent Detection
  ↓
Workspace Selection
  ↓
Vector Search
  ↓
Relevant Context Assembly
  ↓
Model Selection
  ↓
Answer Generation
  ↓
Optional Memory Update
```

### 22.2 Retrieval-Regeln

- Nur Inhalte abrufen, auf die der Benutzer Zugriff hat.
- Quellen mitgeben.
- Metadaten auswerten.
- Alte oder unsichere Quellen niedriger gewichten.
- Admin-Wissen nicht normalen Usern anzeigen.
- Private User-Konversationen nicht workspaceweit verwenden, außer erlaubt.

---

## 23. Datenmodell

### 23.1 PostgreSQL-Tabellen

Empfohlene Tabellen:

```text
users
roles
sessions
totp_secrets
workspaces
agents
tools
model_profiles
model_providers
conversations
messages
approvals
audit_logs
documents
document_chunks
vector_sources
swisschat_accounts
system_events
```

### 23.2 Beispiel: `users`

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    updated_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### 23.3 Beispiel: `approvals`

```sql
CREATE TABLE approvals (
    id UUID PRIMARY KEY,
    requested_by UUID NOT NULL,
    approved_by UUID,
    agent_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    action_name TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL,
    request_payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT now(),
    approved_at TIMESTAMP
);
```

---

## 24. Docker-Architektur

### 24.1 Services

Empfohlene Services:

```yaml
services:
  tessa-api:
    description: Backend API and orchestrator

  tessa-web:
    description: Web UI

  litellm:
    description: Multi-model gateway

  postgres:
    description: Relational database

  qdrant:
    description: Vector database

  redis:
    description: Queue, cache, background jobs

  worker:
    description: Ingestion, vectorization, background tasks

  nginx:
    description: Reverse proxy and TLS termination
```

### 24.2 Beispiel `docker-compose.yml`

```yaml
version: "3.9"

services:
  tessa-api:
    build: ./services/api
    container_name: tessa-api
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
      - qdrant
      - litellm
    networks:
      - tessa-internal

  tessa-web:
    build: ./services/web
    container_name: tessa-web
    restart: unless-stopped
    depends_on:
      - tessa-api
    networks:
      - tessa-internal

  worker:
    build: ./services/worker
    container_name: tessa-worker
    restart: unless-stopped
    env_file:
      - .env
    depends_on:
      - postgres
      - redis
      - qdrant
    networks:
      - tessa-internal

  litellm:
    image: ghcr.io/berriai/litellm:main-latest
    container_name: tessa-litellm
    restart: unless-stopped
    env_file:
      - .env
    networks:
      - tessa-internal

  postgres:
    image: postgres:16
    container_name: tessa-postgres
    restart: unless-stopped
    environment:
      POSTGRES_DB: tessa
      POSTGRES_USER: tessa
      POSTGRES_PASSWORD: change_me
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - tessa-internal

  qdrant:
    image: qdrant/qdrant:latest
    container_name: tessa-qdrant
    restart: unless-stopped
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - tessa-internal

  redis:
    image: redis:7
    container_name: tessa-redis
    restart: unless-stopped
    networks:
      - tessa-internal

  nginx:
    image: nginx:latest
    container_name: tessa-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./infra/nginx:/etc/nginx/conf.d
      - ./infra/certs:/etc/letsencrypt
    depends_on:
      - tessa-web
      - tessa-api
    networks:
      - tessa-internal

volumes:
  postgres_data:
  qdrant_data:

networks:
  tessa-internal:
    driver: bridge
```

---

## 25. Nginx Routing

### 25.1 Ziel

```text
https://tessa.ki-c.pro
```

soll Web-UI und API ausliefern.

### 25.2 Routing

```text
/          → tessa-web
/api       → tessa-api
/ws        → tessa-api websocket
/webhook   → tessa-api SwissChat webhook
```

### 25.3 Beispiel

```nginx
server {
    listen 80;
    server_name tessa.ki-c.pro;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tessa.ki-c.pro;

    ssl_certificate /etc/letsencrypt/live/tessa.ki-c.pro/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tessa.ki-c.pro/privkey.pem;

    location /api/ {
        proxy_pass http://tessa-api:8000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }

    location /webhook/ {
        proxy_pass http://tessa-api:8000/webhook/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws/ {
        proxy_pass http://tessa-api:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location / {
        proxy_pass http://tessa-web:3000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 26. SwissChat Integration

### 26.1 Anforderungen

Der SwissChat-Kanal muss:

- eingehende Nachrichten empfangen,
- Benutzer zuordnen,
- Conversation State speichern,
- Antworten an SwissChat senden,
- Approval-Anfragen darstellen,
- optional Dokumente und Medien entgegennehmen,
- Admin-Befehle nur nach Berechtigung ausführen.

### 26.2 User Linking

```text
SwissChat User
  ↓
Linking Code
  ↓
Tessa Web-UI
  ↓
TOTP Bestätigung
  ↓
SwissChat Account wird User zugeordnet
```

### 26.3 SwissChat-Befehle

Beispiele:

```text
/help
/agent devops
/workspace default
/status
/approve <id>
/deny <id>
```

---

## 27. Vektor-Ingestion

### 27.1 Dokumentenfluss

```text
Upload
  ↓
File Type Detection
  ↓
Text Extraction
  ↓
Chunking
  ↓
Embedding
  ↓
Qdrant Storage
  ↓
Metadata in PostgreSQL
```

### 27.2 Unterstützte Formate Version 1

```text
.md
.txt
.pdf
.docx
.html
.csv
.json
.log
```

### 27.3 Später

```text
.xlsx
.pptx
.eml
.msg
images with OCR
audio transcription
video transcription
```

---

## 28. Audit und Logging

### 28.1 Was wird protokolliert?

- Logins
- fehlgeschlagene Logins
- TOTP-Fehler
- Modellaufrufe
- Tool-Aufrufe
- Shell-Kommandos
- Approval-Anfragen
- Freigaben
- abgelehnte Aktionen
- Änderungen an Policies
- Änderungen an Modellen
- Vektor-Ingestion
- Admin-Aktionen

### 28.2 Audit-Eintrag

```yaml
audit:
  id: uuid
  timestamp: datetime
  user_id: uuid
  agent_id: string
  action: string
  risk_level: low | medium | high | critical
  status: success | denied | failed | pending_approval
  details: json
```

---

## 29. Sicherheit

### 29.1 Grundprinzipien

- Keine Provider-Keys im Frontend.
- Keine internen Dienste öffentlich.
- Alle Admin-Aktionen auditieren.
- Riskante Aktionen nur mit Approval.
- TOTP verpflichtend.
- Secrets nur in `.env` oder Secret Manager.
- Backups verschlüsseln.
- Vektorzugriff nach Berechtigung filtern.
- Shell-Tools strikt whitelisten.

### 29.2 Shell-Sicherheit

Keine freie Shell in Version 1.

Stattdessen:

```text
Command Registry
Command Templates
Risk Classification
Approval Engine
Execution Sandbox
Audit Log
```

Beispiel erlaubter Befehl:

```yaml
command:
  name: nginx_test
  command: nginx -t
  risk: low
  approval_required: false
```

Beispiel riskanter Befehl:

```yaml
command:
  name: nginx_reload
  command: systemctl reload nginx
  risk: high
  approval_required: true
```

---

## 30. Repository-Struktur

Empfohlene Struktur:

```text
tessa/
├── README.md
├── docker-compose.yml
├── .env.example
├── services/
│   ├── api/
│   ├── web/
│   └── worker/
├── infra/
│   ├── nginx/
│   ├── scripts/
│   └── systemd/
├── workspaces/
│   └── company-default/
│       ├── SOUL.md
│       ├── AGENTS.md
│       ├── TOOLS.md
│       ├── POLICIES.md
│       ├── MEMORY.md
│       ├── MODELS.md
│       ├── ROUTING.md
│       ├── VECTOR.md
│       ├── APPROVALS.md
│       ├── skills/
│       └── config/
│           └── workspace.yaml
├── docs/
│   ├── architecture.md
│   ├── security.md
│   └── deployment.md
└── tests/
```

---

## 31. API-Konzept

### 31.1 Endpunkte

```text
POST /api/auth/login
POST /api/auth/totp/verify
POST /api/auth/logout

GET  /api/me
GET  /api/workspaces
GET  /api/agents

POST /api/chat
GET  /api/conversations
GET  /api/conversations/{id}

POST /api/documents/upload
POST /api/documents/{id}/vectorize

POST /api/tools/execute
GET  /api/approvals
POST /api/approvals/{id}/approve
POST /api/approvals/{id}/deny

POST /api/webhook/swisschat

GET  /api/admin/users
POST /api/admin/users
GET  /api/admin/audit
GET  /api/admin/models
POST /api/admin/models
```

---

## 32. Implementierungsphasen

### Phase 1: Fundament

- Ubuntu Server vorbereiten
- DNS `tessa.ki-c.pro`
- Docker Compose
- Nginx + TLS
- PostgreSQL
- Basis API
- Web-UI Skeleton
- Benutzerlogin mit TOTP

### Phase 2: Agent Core

- Workspace Loader
- `SOUL.md` Parser
- `AGENTS.md` Parser
- `TOOLS.md` Parser
- Agent Orchestrator
- einfache Chat-Funktion
- LiteLLM-Anbindung

### Phase 3: Vektor-System

- Qdrant hinzufügen
- Dokument-Ingestion
- Embeddings
- Vector Search
- Retrieval in Chat-Antworten
- `VECTOR.md`

### Phase 4: SwissChat

- SwissChat Webhook
- User Linking
- Chat Routing
- einfache Antworten
- Approval-Nachrichten

### Phase 5: Tool Engine

- Tool Registry
- Shell Readonly Tools
- Docker Status Tools
- Nginx Test Tools
- Audit Logging
- Approval Engine

### Phase 6: Admin Autonomie

- Admin Panel für Agentenrechte
- Autonomiestufen
- Approval-Konfiguration
- Scoped Auto Actions
- Tessa Self-Management Tools

### Phase 7: Erweiterung

- externe Model Nodes
- RAG-Verbesserungen
- Dokumenttypen erweitern
- Monitoring
- Backup
- CI/CD
- Multi-Workspace

---

## 33. Acceptance Criteria für Version 1

Version 1 gilt als funktionsfähig, wenn:

- `https://tessa.ki-c.pro` erreichbar ist.
- Benutzer sich mit Benutzername, Passwort und TOTP anmelden können.
- Web-UI Chat funktioniert.
- mindestens zwei Modellprofile nutzbar sind.
- Workspace-Dateien geladen werden.
- `SOUL.md`, `AGENTS.md`, `TOOLS.md` und `POLICIES.md` wirksam sind.
- Dokumente hochgeladen und vektorisiert werden können.
- Vektor-Suche in Antworten genutzt wird.
- SwissChat-Nachrichten verarbeitet werden können.
- Tool-Aufrufe auditierbar sind.
- riskante Aktionen Approval benötigen.
- Admins Agentenrechte konfigurieren können.
- keine internen Services öffentlich erreichbar sind.

---

## 34. Offene technische Entscheidungen

Folgende Punkte muss der Entwickler vor Umsetzung final klären:

1. Programmiersprache Backend:
   - Python/FastAPI
   - Node.js/NestJS
   - Go

2. Web-Frontend:
   - React
   - Next.js
   - Vue

3. SwissChat API:
   - Webhook-Verhalten
   - Authentifizierung
   - Nachrichtenformat
   - Medienhandling

4. Embedding-Modell:
   - OpenAI Embeddings
   - lokales Embedding-Modell
   - hybrider Ansatz

5. Vektor-Datenbank:
   - Qdrant final empfohlen
   - pgvector als Alternative

6. Secrets:
   - `.env`
   - Docker Secrets
   - Vault
   - Cloud Secret Manager

---

## 35. Empfehlung für Technologie-Stack

Empfohlene erste Umsetzung:

```yaml
backend: Python FastAPI
frontend: Next.js oder React
database: PostgreSQL
vector_db: Qdrant
queue: Redis
model_gateway: LiteLLM
reverse_proxy: Nginx
deployment: Docker Compose
auth: username/password + TOTP
os: Ubuntu 24.04 LTS
```

Begründung:

- schnelle Umsetzung,
- gute KI-Ökosysteme,
- einfache Erweiterbarkeit,
- gute Docker-Unterstützung,
- robuste API-Struktur,
- einfache Integration von Embeddings und Vektor-Datenbanken.

---

## 36. Zusammenfassung

Tessa soll als zentrale Firmen-KI-Instanz unter `tessa.ki-c.pro` entstehen.

Kernprinzipien:

```text
OpenClaw-artige Steuerdateien
+
Web-UI
+
SwissChat-Kanal
+
Benutzername/TOTP Login
+
Multi-Model Gateway
+
separate Modellinstanzen
+
Vektor-Datenbank
+
Tool-Berechtigungen
+
Approval Gates
+
admin-konfigurierbare Autonomie
+
langfristige Instanz-Selbstverwaltung
```

Die Plattform soll initial kontrolliert starten, aber so gebaut werden, dass sie perspektivisch die komplette eigene Instanz analysieren, warten und verwalten kann.

Die Autonomie wird dabei nicht hart im Code festgelegt, sondern durch Admins, Policies, Tools und Workspace-Dateien gesteuert.
