"""Sandboxed command execution: argv only, no shell, timeout-bounded."""

from __future__ import annotations

import subprocess

TIMEOUT = 30


def run(argv: list[str]) -> dict:
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
