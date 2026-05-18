"""Phase 4: SwissChat HMAC signature verification (protocol §4.1)."""

import hashlib
import hmac

from app.channels.swisschat import expected_signature, verify_signature

SECRET = "test-webhook-secret"
BODY = b'{"type":"message","plaintext":"hi"}'


def test_expected_signature_matches_spec():
    want = "sha256=" + hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
    assert expected_signature(BODY, SECRET) == want


def test_verify_ok():
    sig = expected_signature(BODY, SECRET)
    assert verify_signature(BODY, sig, SECRET) is True


def test_verify_rejects_bad_and_empty():
    assert verify_signature(BODY, "sha256=deadbeef", SECRET) is False
    assert verify_signature(BODY, None, SECRET) is False
    assert verify_signature(BODY, expected_signature(BODY, SECRET), "") is False
    # tampered body
    assert verify_signature(b"tampered", expected_signature(BODY, SECRET), SECRET) is False
