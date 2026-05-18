"""Command registry — the ONLY commands Tessa may run (§29.2).

No free shell. Each entry is a fixed argv. Commands that need a parameter
declare `arg_pattern`; the caller-supplied `target` must fully match it and
is appended as a single argv element (never shell-interpreted).

risk: low | medium | high | critical
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Command:
    name: str
    argv: list[str]            # may be empty when `internal` is set
    tool: str                  # category, must be in the agent's TOOLS list
    risk: str
    approval_required: bool
    description: str
    arg_pattern: str | None = None  # regex for an optional single argument
    internal: str | None = None     # key into INTERNAL_ACTIONS; in-process tool
    payload_schema: dict | None = None  # JSON schema for an internal-tool payload


REGISTRY: dict[str, Command] = {
    # ---- shell_readonly (low, no approval) ----
    "sys_uptime": Command("sys_uptime", ["uptime"], "shell_readonly", "low",
                          False, "System uptime/load"),
    "disk_free": Command("disk_free", ["df", "-h"], "shell_readonly", "low",
                         False, "Disk usage"),
    "mem_free": Command("mem_free", ["free", "-h"], "shell_readonly", "low",
                        False, "Memory usage"),
    "list_dir": Command("list_dir", ["ls", "-la"], "shell_readonly", "low",
                        False, "List a directory (target=path)",
                        arg_pattern=r"/[\w./-]{0,200}"),
    "read_file": Command("read_file", ["cat"], "shell_readonly", "low",
                         False, "Read a file (target=path)",
                         arg_pattern=r"/[\w./-]{1,200}"),
    # ---- logs / status (low) ----
    "docker_ps": Command("docker_ps", ["docker", "ps", "--format",
                         "{{.Names}}\t{{.Status}}"], "docker", "low", False,
                         "Running containers"),
    "docker_logs": Command("docker_logs", ["docker", "logs", "--tail", "100"],
                           "docker", "low", False,
                           "Container logs (target=container)",
                           arg_pattern=r"[A-Za-z0-9_.-]{1,64}"),
    "nginx_test": Command("nginx_test", ["nginx", "-t"], "nginx", "low",
                          False, "Validate nginx config"),
    "service_status": Command("service_status",
                              ["systemctl", "status", "--no-pager"],
                              "systemd", "low", False,
                              "Service status (target=unit)",
                              arg_pattern=r"[A-Za-z0-9_.@-]{1,64}"),
    # ---- write / high risk (approval required) ----
    "nginx_reload": Command("nginx_reload", ["systemctl", "reload", "nginx"],
                            "nginx", "high", True, "Reload nginx"),
    "service_restart": Command("service_restart", ["systemctl", "restart"],
                               "systemd", "high", True,
                               "Restart a service (target=unit)",
                               arg_pattern=r"[A-Za-z0-9_.@-]{1,64}"),
    "docker_compose_down": Command("docker_compose_down",
                                   ["docker", "compose", "down"], "docker",
                                   "high", True, "Stop the stack"),
    "apt_install": Command("apt_install",
                           ["apt-get", "install", "-y"], "shell_write",
                           "high", True, "Install a package (target=pkg)",
                           arg_pattern=r"[a-z0-9][a-z0-9.+-]{0,64}"),
    # ---- critical (superadmin + TOTP) ----
    "delete_path": Command("delete_path", ["rm", "-rf"], "shell_write",
                           "critical", True,
                           "Delete a path (target=path)",
                           arg_pattern=r"/[\w./-]{2,200}"),
    # ---- workspace self-editing (in-process; the agent's own files) ----
    "workspace_read": Command(
        "workspace_read", [], "workspace", "low", False,
        "Read a workspace steering file. payload: {file: SOUL|AGENTS|TOOLS|"
        "POLICIES|MEMORY|MODELS|ROUTING|VECTOR|APPROVALS, workspace?: slug}",
        internal="workspace_read",
        payload_schema={
            "type": "object",
            "required": ["file"],
            "properties": {
                "file": {"type": "string",
                         "enum": ["SOUL", "AGENTS", "TOOLS", "POLICIES",
                                  "MEMORY", "MODELS", "ROUTING", "VECTOR",
                                  "APPROVALS"]},
                "workspace": {"type": "string"},
            },
        },
    ),
    "workspace_write": Command(
        "workspace_write", [], "workspace", "medium", False,
        "Overwrite a workspace steering file. The agent should call this "
        "when its understanding of itself has changed. payload: "
        "{file, content, reason}. Audit captures a unified diff.",
        internal="workspace_write",
        payload_schema={
            "type": "object",
            "required": ["file", "content", "reason"],
            "properties": {
                "file": {"type": "string",
                         "enum": ["SOUL", "AGENTS", "TOOLS", "POLICIES",
                                  "MEMORY", "MODELS", "ROUTING", "VECTOR",
                                  "APPROVALS"]},
                "content": {"type": "string"},
                "reason": {"type": "string",
                           "description": "One short sentence — why you "
                                          "are changing this file."},
                "workspace": {"type": "string"},
            },
        },
    ),
}

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def get(name: str) -> Command | None:
    return REGISTRY.get(name)


def build_argv(cmd: Command, target: str | None) -> list[str]:
    if cmd.arg_pattern:
        if target is None or not re.fullmatch(cmd.arg_pattern, target):
            raise ValueError(f"Invalid or missing target for {cmd.name}")
        return [*cmd.argv, target]
    if target:
        raise ValueError(f"{cmd.name} takes no target")
    return list(cmd.argv)
