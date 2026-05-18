"""Phase 1 unit tests for security primitives (no DB needed)."""

import pyotp

from app.security import (
    decrypt,
    encrypt,
    hash_password,
    new_totp_secret,
    verify_password,
    verify_totp,
)


def test_password_hash_roundtrip():
    h = hash_password("correct horse battery staple")
    assert h != "correct horse battery staple"
    assert verify_password("correct horse battery staple", h)
    assert not verify_password("wrong", h)


def test_encrypt_roundtrip():
    secret = "sk-provider-12345"
    token = encrypt(secret)
    assert token != secret
    assert decrypt(token) == secret


def test_totp_verify():
    secret = new_totp_secret()
    code = pyotp.TOTP(secret).now()
    assert verify_totp(secret, code)
    assert not verify_totp(secret, "000000")
