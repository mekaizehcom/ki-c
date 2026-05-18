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
