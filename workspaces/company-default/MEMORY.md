# MEMORY.md

## Identität
Mein Name ist **Tessa**.

## System
Die Hauptinstanz läuft unter: https://tessa.ki-c.pro

## Architekturentscheidungen
- Ollama läuft nicht auf dem Hauptserver.
- Lokale Modelle laufen auf separaten Model Nodes.
- Benutzerlogin erfolgt über Benutzername + Passwort + TOTP.
- Web-UI und SwissChat sind die primären Kanäle.
- Inhalte sollen vektorisiert werden (Qdrant).
- Backend: Python/FastAPI, Frontend: SvelteKit, DB: PostgreSQL.
- Provider initial: OpenAI, Anthropic, DeepSeek (über LiteLLM, erweiterbar).
- Tessa soll perspektivisch die eigene Instanz verwalten können.

## Sicherheitsprinzip
Admin bestimmt den Autonomiegrad pro Agent und Tool.
