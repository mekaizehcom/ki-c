# VECTOR.md

## Zu vektorisierende Inhalte
- Chatverläufe (Web-UI, SwissChat)
- hochgeladene Dokumente
- Markdown-Dateien
- technische Logs
- Projektwissen / Memory-Einträge
- relevante Systemkonfigurationen
- Ergebnisse abgeschlossener Aufgaben
- Skill-Dokumentationen

## Datenklassen
```yaml
vector_classes:
  conversation:   { retention: configurable, default_visibility: user_private }
  document:       { retention: persistent,    default_visibility: workspace }
  system_knowledge:{ retention: persistent,   default_visibility: admin }
  task_result:    { retention: persistent,    default_visibility: workspace }
  memory:         { retention: persistent,    default_visibility: workspace }
```

## Sichtbarkeiten
user_private | team | workspace | admin | global

## Chunking
```yaml
chunking:
  default_chunk_size_tokens: 800
  overlap_tokens: 120
  preserve_headings: true
  preserve_code_blocks: true
  preserve_tables: true
```

## Metadaten
Jeder Vektor-Eintrag enthält: id, source_type, source_id, workspace_id,
user_id (optional), visibility, created_at, updated_at, tags, checksum.
