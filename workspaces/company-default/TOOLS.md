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

## workspace

Self-editing of the agent's own steering files.

Erlaubt:
- workspace_read  (SOUL, AGENTS, TOOLS, POLICIES, MEMORY, MODELS,
                   ROUTING, VECTOR, APPROVALS)
- workspace_write (gleiche Dateien)

Approval:
nicht erforderlich. SOUL.md sagt explizit: "These files _are_ your memory.
Read them. Update them." Audit-Log erfasst die vollständige Diff.

Erwartung:
Wenn die Agent ihre SOUL ändert, soll sie das in der Konversation
erwähnen — siehe SOUL.md "If you change this file, tell the user".

---

## swisschat

Erlaubt:
- Nachrichten lesen
- Antworten senden
- Approval-Nachrichten senden
- Benutzerzuordnung prüfen

E-Mail-, Zahlungs- oder produktive externe Aktionen sind nicht Teil dieses Tools.
