"""SSH channel: input validation. No live network in CI."""

import pytest

from app.channels import ssh as ssh_channel


def test_validate_label_rejects_invalid():
    # Uppercase is OK (lowercased silently); these are the genuinely
    # invalid forms.
    for bad in ("", "with space", "-leading-dash", "x" * 50, "label!"):
        with pytest.raises(ValueError):
            ssh_channel._validate_label(bad)


def test_validate_label_accepts_normal():
    assert ssh_channel._validate_label("staging") == "staging"
    assert ssh_channel._validate_label("prod-eu1") == "prod-eu1"
    assert ssh_channel._validate_label("X-EU1") == "x-eu1"  # lowercased


def test_validate_label_rejects_reserved():
    for r in ssh_channel.RESERVED_LABELS:
        with pytest.raises(ValueError):
            ssh_channel._validate_label(r)


def test_upsert_rejects_bad_inputs():
    class _StubDB:
        def get(self, *a, **k): return None
        def add(self, *a, **k): pass
        def commit(self): pass

    db = _StubDB()
    bad_pk = "not a key"
    pem = "-----BEGIN PRIVATE KEY-----\nx\n-----END PRIVATE KEY-----"
    with pytest.raises(ValueError):
        ssh_channel.upsert_host(db, label="x", host="", user="u", port=22,
                                private_key=pem)
    with pytest.raises(ValueError):
        ssh_channel.upsert_host(db, label="x", host="h", user="u", port=99999,
                                private_key=pem)
    with pytest.raises(ValueError):
        ssh_channel.upsert_host(db, label="x", host="h", user="u", port=22,
                                private_key=bad_pk)
