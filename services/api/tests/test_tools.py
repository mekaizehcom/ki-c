"""Phase 5: command registry argument safety + risk classification."""

import pytest

from app.tools.registry import REGISTRY, build_argv, get


def test_no_target_command_rejects_target():
    cmd = get("sys_uptime")
    assert build_argv(cmd, None) == ["uptime"]
    with pytest.raises(ValueError):
        build_argv(cmd, "anything")


def test_target_pattern_enforced_blocks_injection():
    cmd = get("read_file")  # arg_pattern: /[\w./-]{1,200}
    assert build_argv(cmd, "/etc/hostname") == ["cat", "/etc/hostname"]
    for bad in ["; rm -rf /", "/etc/passwd; cat /e", "$(whoami)", "../../x", "relative"]:
        with pytest.raises(ValueError):
            build_argv(cmd, bad)


def test_unknown_command():
    assert get("definitely_not_a_command") is None


def test_risk_levels_present_and_high_requires_approval():
    assert get("nginx_reload").risk == "high"
    assert get("nginx_reload").approval_required is True
    assert get("delete_path").risk == "critical"
    # every registry entry has a sane risk
    assert all(c.risk in {"low", "medium", "high", "critical"}
               for c in REGISTRY.values())
