"""Tool execution: argv-subprocess OR in-process action.

The permission engine decides whether a tool runs at all; this module is
the only place that actually executes anything. argv → subprocess (no
shell, timeout-bounded). internal → call into INTERNAL_ACTIONS.
"""

from __future__ import annotations

import json
import subprocess
import traceback
from typing import Any

from app.tools.internal import INTERNAL_ACTIONS
from app.tools.registry import Command

TIMEOUT = 30


def run(argv: list[str]) -> dict:
    """Subprocess tool. Returns {exit_code, stdout, stderr}."""
    try:
        p = subprocess.run(  # noqa: S603 - argv is from the fixed registry
            argv,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            shell=False,
            check=False,
        )
        return {
            "exit_code": p.returncode,
            "stdout": p.stdout[-8000:],
            "stderr": p.stderr[-4000:],
        }
    except FileNotFoundError as exc:
        return {"exit_code": 127, "stdout": "", "stderr": f"not available here: {exc}"}
    except subprocess.TimeoutExpired:
        return {"exit_code": 124, "stdout": "", "stderr": f"timeout after {TIMEOUT}s"}
    except Exception as exc:  # noqa: BLE001
        return {"exit_code": 1, "stdout": "", "stderr": str(exc)}


def run_internal(cmd: Command, payload: dict, ctx: dict[str, Any]) -> dict:
    """In-process tool. Returns the same {exit_code, stdout, stderr} shape so
    auditing and result-passing stays uniform across both paths."""
    if not cmd.internal:
        return {"exit_code": 1, "stdout": "", "stderr": "no internal action set"}
    fn = INTERNAL_ACTIONS.get(cmd.internal)
    if fn is None:
        return {"exit_code": 1, "stdout": "",
                "stderr": f"unknown internal action: {cmd.internal}"}
    try:
        result = fn(payload or {}, ctx)
        return {"exit_code": 0,
                "stdout": json.dumps(result, ensure_ascii=False, indent=2),
                "stderr": "",
                "result": result}
    except ValueError as exc:
        return {"exit_code": 2, "stdout": "", "stderr": str(exc)}
    except Exception:  # noqa: BLE001
        return {"exit_code": 1, "stdout": "", "stderr": traceback.format_exc()}
