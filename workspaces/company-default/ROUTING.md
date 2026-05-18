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
Wenn ein Modell nicht erreichbar ist, verwende das nächstniedrigere
erlaubte Profil. Wenn kein Provider-Key konfiguriert ist, verwende
das Modell `mock-echo`.
