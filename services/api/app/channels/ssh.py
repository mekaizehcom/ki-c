"""SSH client for the multi-host sandbox.

Tessa's brain runs on the base host (locked down, registry-whitelisted
tools only). For productive work — deployments, nginx, certbot — the
agent reaches out to SEPARATE hosts over SSH. Each host is registered
under a unique `label` (e.g. "staging", "prod-eu1") so the agent can
pick by name. Free-form shell is intentional on those hosts.

Storage: `ssh_hosts` table. Private keys Fernet-encrypted via
app.security.encrypt/decrypt.

Host key verification: TOFU on first connect (auto-accept, store
fingerprint), strict-verify after. The known_hosts file lives on the
persistent volume at /var/lib/tessa/ssh/known_hosts and is shared
across all hosts (one file, multiple entries keyed by host+port).
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SshHost
from app.security import decrypt, encrypt

SSH_STATE_DIR = "/var/lib/tessa/ssh"
KNOWN_HOSTS = os.path.join(SSH_STATE_DIR, "known_hosts")
DEFAULT_TIMEOUT = 60

LABEL_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,40}")
RESERVED_LABELS = {"localhost", "local", "tessa", "self"}


def _validate_label(label: str) -> str:
    label = (label or "").strip().lower()
    if not LABEL_RE.fullmatch(label):
        raise ValueError(
            "label must be 1-41 chars, lowercase letters/digits/_/-, "
            "starting with a letter or digit"
        )
    if label in RESERVED_LABELS:
        raise ValueError(f"label '{label}' is reserved")
    return label


def _to_public(row: SshHost) -> dict:
    return {
        "label": row.label,
        "host": row.host,
        "user": row.username,
        "port": row.port,
        "description": row.description or "",
        "enabled": row.enabled,
        "fingerprint": row.fingerprint,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


# ---- public CRUD ----

def list_hosts(db: Session) -> list[dict]:
    rows = db.scalars(select(SshHost).order_by(SshHost.label))
    return [_to_public(r) for r in rows]


def get_host(db: Session, label: str) -> dict | None:
    row = db.get(SshHost, label.strip().lower())
    return _to_public(row) if row else None


def upsert_host(
    db: Session,
    *,
    label: str,
    host: str,
    user: str = "ubuntu",
    port: int = 22,
    private_key: str,
    description: str = "",
    created_by=None,
) -> dict:
    label = _validate_label(label)
    host = (host or "").strip()
    user = (user or "ubuntu").strip()
    if not host:
        raise ValueError("host is required")
    if not 1 <= int(port) <= 65535:
        raise ValueError("port must be 1..65535")
    if "BEGIN" not in (private_key or "") or "PRIVATE KEY" not in private_key:
        raise ValueError("private_key must be a PEM-encoded private key")
    if not private_key.endswith("\n"):
        private_key += "\n"

    row = db.get(SshHost, label)
    if row is None:
        row = SshHost(label=label, host=host, username=user, port=int(port),
                      description=description,
                      private_key_encrypted=encrypt(private_key),
                      created_by=created_by)
        db.add(row)
    else:
        # If host/port changed, the old known_hosts fingerprint is no longer
        # meaningful — clear it so TOFU re-runs.
        if row.host != host or row.port != int(port):
            _forget_host_entry(row.host, row.port)
            row.fingerprint = None
        row.host = host
        row.username = user
        row.port = int(port)
        row.description = description
        row.private_key_encrypted = encrypt(private_key)
        row.enabled = True
    db.commit()
    return _to_public(row)


def forget_host(db: Session, label: str) -> bool:
    label = label.strip().lower()
    row = db.get(SshHost, label)
    if not row:
        return False
    _forget_host_entry(row.host, row.port)
    db.delete(row)
    db.commit()
    return True


# ---- core SSH run ----

def run(
    db: Session,
    label: str,
    command: str,
    *,
    cwd: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Run an arbitrary shell command on the labeled host."""
    label_norm = (label or "").strip().lower()
    row = db.get(SshHost, label_norm)
    if not row:
        return {"exit_code": 1, "stdout": "",
                "stderr": (f"unknown ssh host label '{label}'. "
                           f"Configured: " + ", ".join(
                               r.label for r in db.scalars(select(SshHost))
                           ) or "(none)"),
                "host": None, "label": label_norm}
    if not row.enabled:
        return {"exit_code": 1, "stdout": "",
                "stderr": f"host '{label_norm}' is disabled",
                "host": f"{row.username}@{row.host}:{row.port}",
                "label": label_norm}

    os.makedirs(SSH_STATE_DIR, exist_ok=True)
    os.chmod(SSH_STATE_DIR, 0o700)

    keyf = tempfile.NamedTemporaryFile(mode="w", delete=False, dir=SSH_STATE_DIR)
    try:
        keyf.write(decrypt(row.private_key_encrypted))
        keyf.flush()
        os.chmod(keyf.name, 0o600)
        keyf.close()

        first_time = not row.fingerprint or not _has_host(row.host, row.port)
        argv = [
            "ssh",
            "-i", keyf.name,
            "-p", str(row.port),
            "-o", "BatchMode=yes",
            "-o", "PasswordAuthentication=no",
            "-o", "PubkeyAuthentication=yes",
            "-o", "IdentitiesOnly=yes",
            "-o", f"UserKnownHostsFile={KNOWN_HOSTS}",
            "-o", (
                "StrictHostKeyChecking=accept-new" if first_time
                else "StrictHostKeyChecking=yes"
            ),
            "-o", f"ConnectTimeout={min(15, timeout)}",
            f"{row.username}@{row.host}",
        ]
        payload = (f"cd {shlex.quote(cwd)} && {command}") if cwd else command
        argv.append(payload)

        try:
            p = subprocess.run(
                argv, capture_output=True, text=True,
                timeout=timeout, shell=False, check=False,
            )
            result = {
                "exit_code": p.returncode,
                "stdout": p.stdout[-8000:],
                "stderr": p.stderr[-4000:],
                "host": f"{row.username}@{row.host}:{row.port}",
                "label": row.label,
            }
        except subprocess.TimeoutExpired:
            result = {"exit_code": 124, "stdout": "",
                      "stderr": f"timeout after {timeout}s",
                      "host": f"{row.username}@{row.host}:{row.port}",
                      "label": row.label}

        # First-time success: record the fingerprint so future calls
        # use strict verification.
        if first_time and result["exit_code"] in (0, 1, 2):
            fp = _read_fingerprint(row.host, row.port)
            if fp:
                row.fingerprint = fp
                db.commit()
        return result
    finally:
        try:
            os.unlink(keyf.name)
        except OSError:
            pass


def test_connection(db: Session, label: str) -> dict:
    """Quick probe used by the admin UI."""
    return run(db, label, "id; hostname; uname -srm; uptime -p")


# ---- internals: known_hosts management ----

def _has_host(host: str, port: int) -> bool:
    if not os.path.exists(KNOWN_HOSTS):
        return False
    bracket = f"[{host}]:{port}" if port != 22 else host
    try:
        p = subprocess.run(
            ["ssh-keygen", "-F", bracket, "-f", KNOWN_HOSTS],
            capture_output=True, text=True, check=False, timeout=5,
        )
        return p.returncode == 0 and bool(p.stdout.strip())
    except Exception:
        return False


def _forget_host_entry(host: str, port: int) -> None:
    if not os.path.exists(KNOWN_HOSTS):
        return
    bracket = f"[{host}]:{port}" if port != 22 else host
    try:
        subprocess.run(
            ["ssh-keygen", "-R", bracket, "-f", KNOWN_HOSTS],
            capture_output=True, check=False, timeout=5,
        )
    except Exception:
        pass


def _read_fingerprint(host: str, port: int) -> str | None:
    if not shutil.which("ssh-keyscan") or not shutil.which("ssh-keygen"):
        return None
    try:
        scan = subprocess.run(
            ["ssh-keyscan", "-p", str(port), "-T", "5", host],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if scan.returncode != 0 or not scan.stdout.strip():
            return None
        with tempfile.NamedTemporaryFile("w", delete=False) as tmp:
            tmp.write(scan.stdout)
            tmpname = tmp.name
        try:
            fp = subprocess.run(
                ["ssh-keygen", "-l", "-f", tmpname],
                capture_output=True, text=True, check=False, timeout=5,
            )
            line = (fp.stdout.strip().splitlines() or [""])[0]
            return line or None
        finally:
            os.unlink(tmpname)
    except Exception:
        return None
