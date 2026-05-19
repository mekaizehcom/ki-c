"""SSH channel — input validation only (no live network)."""

import pytest

from app.channels import ssh as ssh_channel


class _StubDB:
    def __init__(self): self.saved = None
    def get(self, *a, **k): return None
    def commit(self): pass
    def add(self, x): self.saved = x
    def delete(self, x): pass


def test_configure_rejects_blank_host():
    with pytest.raises(ValueError):
        ssh_channel.configure(_StubDB(), host="", user="ubuntu", port=22,
                              private_key="-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----")


def test_configure_rejects_bad_port():
    with pytest.raises(ValueError):
        ssh_channel.configure(_StubDB(), host="x", user="u", port=99999,
                              private_key="-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----")


def test_configure_rejects_non_pem_key():
    with pytest.raises(ValueError):
        ssh_channel.configure(_StubDB(), host="x", user="u", port=22,
                              private_key="not a key")
