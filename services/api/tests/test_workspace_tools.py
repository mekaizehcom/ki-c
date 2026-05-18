"""workspace_read / workspace_write internal tools."""

import os
import tempfile

import pytest

from app.tools.internal import ALLOWED_FILES, _resolve_path, workspace_read, workspace_write


def test_resolve_path_only_in_allowed_set():
    with pytest.raises(ValueError):
        _resolve_path("company-default", "NOT_A_FILE")
    with pytest.raises(ValueError):
        _resolve_path("../etc", "SOUL")
    with pytest.raises(ValueError):
        _resolve_path("ok_slug", "SOUL/../../etc/passwd")


def test_allowed_file_set_covers_steering_dir():
    assert ALLOWED_FILES == {
        "SOUL", "AGENTS", "TOOLS", "POLICIES",
        "MEMORY", "MODELS", "ROUTING", "VECTOR", "APPROVALS",
    }


def test_write_requires_reason(monkeypatch, tmp_path):
    from app.config import settings
    monkeypatch.setattr(settings, "tessa_workspaces_dir", str(tmp_path))
    monkeypatch.setattr(settings, "default_workspace", "ws")
    os.makedirs(tmp_path / "ws", exist_ok=True)

    with pytest.raises(ValueError):
        workspace_write(
            {"file": "MEMORY", "content": "hi", "workspace": "ws"}, {}
        )


def test_read_write_roundtrip_and_diff(monkeypatch, tmp_path):
    from app.config import settings
    monkeypatch.setattr(settings, "tessa_workspaces_dir", str(tmp_path))
    monkeypatch.setattr(settings, "default_workspace", "ws")
    os.makedirs(tmp_path / "ws", exist_ok=True)

    r0 = workspace_read({"file": "MEMORY", "workspace": "ws"}, {})
    assert r0["content"] == "" and r0["bytes"] == 0

    w = workspace_write(
        {"file": "MEMORY", "content": "line one\n",
         "reason": "first write", "workspace": "ws"},
        {},
    )
    assert w["bytes"] == 9 and "first write" in w["reason"]

    r1 = workspace_read({"file": "MEMORY", "workspace": "ws"}, {})
    assert r1["content"] == "line one\n"

    w2 = workspace_write(
        {"file": "MEMORY", "content": "line one\nline two\n",
         "reason": "append", "workspace": "ws"},
        {},
    )
    assert "line two" in w2["diff"]
    assert "+line two" in w2["diff"]
