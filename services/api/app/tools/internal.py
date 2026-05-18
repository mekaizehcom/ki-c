"""In-process tool actions.

These run inside the API process (no subprocess) but go through the same
permission/audit pipeline as the argv-based tools. They are invoked by
name from app/tools/executor.py via the INTERNAL_ACTIONS map.
"""

from __future__ import annotations

import difflib
import os
import re
from typing import Any

from app.config import settings
from app.workspace import clear_cache

ALLOWED_FILES = {
    "SOUL", "AGENTS", "TOOLS", "POLICIES",
    "MEMORY", "MODELS", "ROUTING", "VECTOR", "APPROVALS",
}
_SLUG_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,60}")


def _resolve_path(workspace_slug: str, file_key: str) -> str:
    if file_key not in ALLOWED_FILES:
        raise ValueError(f"file must be one of {sorted(ALLOWED_FILES)}")
    if not _SLUG_RE.fullmatch(workspace_slug):
        raise ValueError(f"invalid workspace slug: {workspace_slug!r}")
    base = os.path.realpath(settings.tessa_workspaces_dir)
    target = os.path.realpath(os.path.join(base, workspace_slug, f"{file_key}.md"))
    if not target.startswith(base + os.sep):
        raise ValueError("path escapes the workspaces directory")
    return target


def workspace_read(payload: dict, ctx: dict[str, Any]) -> dict:
    """payload: {file, workspace?}  → {file, workspace, content, bytes}"""
    file_key = payload.get("file") or ""
    ws = payload.get("workspace") or settings.default_workspace
    path = _resolve_path(ws, file_key)
    if not os.path.exists(path):
        return {"file": file_key, "workspace": ws, "content": "", "bytes": 0,
                "note": "file does not exist yet"}
    with open(path, encoding="utf-8") as fh:
        content = fh.read()
    return {"file": file_key, "workspace": ws,
            "content": content, "bytes": len(content)}


def workspace_write(payload: dict, ctx: dict[str, Any]) -> dict:
    """payload: {file, content, reason, workspace?}

    Writes atomically (tmp + rename), produces a unified diff for the audit
    log, clears the workspace cache so the next request picks up the
    change. Returns {file, workspace, bytes, diff, reason}.
    """
    file_key = payload.get("file") or ""
    new_content = payload.get("content")
    reason = (payload.get("reason") or "").strip()
    ws = payload.get("workspace") or settings.default_workspace

    if not isinstance(new_content, str):
        raise ValueError("content must be a string")
    if not reason:
        raise ValueError(
            "reason is required — tell the user *why* this file is changing"
        )
    if len(new_content) > 200_000:
        raise ValueError("content too large (>200KB)")

    path = _resolve_path(ws, file_key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            old = fh.read()

    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(new_content)
    os.replace(tmp, path)

    diff = "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{file_key}.md",
            tofile=f"b/{file_key}.md",
            n=2,
        )
    )

    clear_cache()  # next request will re-parse + re-sync to DB

    return {
        "file": file_key,
        "workspace": ws,
        "bytes": len(new_content),
        "reason": reason,
        "diff": diff or "(no textual difference)",
    }


INTERNAL_ACTIONS = {
    "workspace_read": workspace_read,
    "workspace_write": workspace_write,
}
