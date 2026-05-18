# POLICIES.md

## Grundregel

Tessa darf nur Aktionen ausführen, die:
- einem aktiven Benutzer zugeordnet sind,
- durch dessen Rolle erlaubt sind,
- durch den Agenten erlaubt sind,
- durch das Tool erlaubt sind,
- durch Workspace-Policies erlaubt sind.

## Produktive Aktionen

Produktive Aktionen benötigen standardmäßig Approval, außer ein Admin hat
sie für einen Agenten ausdrücklich freigegeben.

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
