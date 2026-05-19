"""SSH client for the sandbox execution host.

Tessa's brain runs on the base host (locked down, registry-whitelisted
tools only). For productive work — deployments, nginx, certbot — the
agent reaches out to a SEPARATE host over SSH. That host is the
"sandbox" where free-form shell is acceptable. This module is the only
place that opens those connections.

Credentials live in integration_credentials["sandbox_host"]:
  public:  {host, user, port, fingerprint}
  encrypted: {private_key}

Host key verification: TOFU on first connect (auto-accept, store
fingerprint), strict-verify after. The known_hosts file lives on a
persistent volume at /var/lib/tessa/ssh/known_hosts.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import tempfile

from sqlalchemy.orm import Session

from app.integrations import get_credentials, get_public, save_credentials

SANDBOX = "sandbox_host"
SSH_STATE_DIR = "/var/lib/tessa/ssh"
KNOWN_HOSTS = os.path.join(SSH_STATE_DIR, "known_hosts")
DEFAULT_TIMEOUT = 60


# ---- public configure / status ----

def configure(
    db: Session, *, host: str, user: str, port: int, private_key: str,
) -> dict:
    """Save sandbox credentials. Does NOT test the connection — call
    test_connection() separately so the admin sees the result."""
    host = (host or "").strip()
    user = (user or "").strip()
    if not host or not user:
        raise ValueError("host and user are required")
    if not 1 <= port <= 65535:
        raise ValueError("port must be 1..65535")
    if "BEGIN" not in (private_key or "") or "PRIVATE KEY" not in private_key:
        raise ValueError("private_key must be a PEM-encoded private key")
    if not private_key.endswith("\n"):
        private_key += "\n"

    public = {"host": host, "user": user, "port": port, "fingerprint": None}
    save_credentials(db, SANDBOX,
                     secret_data={"private_key": private_key},
                     public=public)
    # Wipe any old known-hosts entries for this host so TOFU re-runs.
    _forget_host(host, port)
    return public


def forget(db: Session) -> None:
    info = get_public(db, SANDBOX)
    if info.get("host"):
        _forget_host(info["host"], info.get("port") or 22)
    from app.integrations import forget as _f
    _f(db, SANDBOX)


def public_info(db: Session) -> dict:
    return get_public(db, SANDBOX)


# ---- core SSH run ----

def run(
    db: Session, command: str, *, cwd: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """Run an arbitrary shell command on the sandbox host. Returns
    {exit_code, stdout, stderr, host}. No argv whitelist — the whole
    point of the sandbox is that the agent has a free shell there."""
    creds = get_credentials(db, SANDBOX)
    public = get_public(db, SANDBOX)
    if not creds or not public.get("host"):
        return {"exit_code": 1, "stdout": "",
                "stderr": "sandbox_host is not configured",
                "host": None}

    host = public["host"]
    user = public["user"]
    port = int(public.get("port") or 22)
    fingerprint = public.get("fingerprint")

    os.makedirs(SSH_STATE_DIR, exist_ok=True)
    os.chmod(SSH_STATE_DIR, 0o700)

    # Write the private key to a temp file (mode 0600), removed after.
    keyf = tempfile.NamedTemporaryFile(mode="w", delete=False, dir=SSH_STATE_DIR)
    try:
        keyf.write(creds["private_key"])
        keyf.flush()
        os.chmod(keyf.name, 0o600)
        keyf.close()

        first_time = not fingerprint or not _has_host(host, port)
        argv = [
            "ssh",
            "-i", keyf.name,
            "-p", str(port),
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
            f"{user}@{host}",
        ]
        # Wrap command for cwd; never compose with shell on our side.
        if cwd:
            payload = f"cd {shlex.quote(cwd)} && {command}"
        else:
            payload = command
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
                "host": f"{user}@{host}:{port}",
            }
        except subprocess.TimeoutExpired:
            result = {"exit_code": 124, "stdout": "",
                      "stderr": f"timeout after {timeout}s",
                      "host": f"{user}@{host}:{port}"}

        # First-time success: record the fingerprint so future calls
        # use strict verification.
        if first_time and result["exit_code"] in (0, 1, 2):
            fp = _read_fingerprint(host, port)
            if fp:
                public["fingerprint"] = fp
                save_credentials(db, SANDBOX,
                                 secret_data=creds, public=public)
        return result
    finally:
        try:
            os.unlink(keyf.name)
        except OSError:
            pass


def test_connection(db: Session) -> dict:
    """Quick probe used by the admin UI."""
    return run(db, "id; hostname; uname -srm; uptime -p")


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


def _forget_host(host: str, port: int) -> None:
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
