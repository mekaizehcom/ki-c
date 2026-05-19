# AGENTS.md

## main
Zweck:
Allgemeiner Firmenassistent. Default-Agent für alle User-Konversationen.
Darf seine eigenen Steering-Dateien editieren UND auf registrierten
SSH-Targets frei arbeiten (Sandbox-Hosts via ssh_exec).

Modellprofil:
default-balanced

Tools:
- search_vector
- read_memory
- write_memory_proposal
- document_reader
- workspace
- remote_shell

Autonomie:
scoped_auto

Erlaubte autonome Aktionen:
- workspace_read
- workspace_write
- ssh_exec

---

## devops
Zweck:
Verwaltung und Analyse der Ubuntu-Serverumgebung. Productive actions
(deployments, nginx, certbot, apt) target the **sandbox host** over SSH,
not the Tessa host itself.

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
- remote_shell
- workspace

Autonomie:
scoped_auto

Erlaubte autonome Aktionen:
- ssh_exec
- workspace_read
- workspace_write

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
Verwaltung der Tessa-Instanz selbst und der registrierten Sandbox-Hosts
(Deploys, Nginx, Certbot, Services).

Modellprofil:
strong-reasoning

Tools:
- tessa_config
- user_admin
- model_admin
- vector_admin
- audit_reader
- service_manager
- workspace
- remote_shell

Autonomie:
scoped_auto

Erlaubte autonome Aktionen:
- workspace_read
- workspace_write
- ssh_exec

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
- workspace

Autonomie:
scoped_auto

Erlaubte autonome Aktionen:
- workspace_read
- workspace_write
