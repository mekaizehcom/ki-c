"""Slash-command helpers — pure, no DB needed for these."""

from app.routers.chat import _approx_tokens, _fmt_bytes, _fmt_duration


def test_approx_tokens_ignores_non_strings():
    msgs = [
        {"role": "system", "content": "hello world"},
        {"role": "user", "content": ""},
        {"role": "assistant", "content": None},
        {"role": "tool", "content": "x" * 40},
    ]
    # 11 + 0 + 0 + 40 = 51 chars / 4 = 12 tokens
    assert _approx_tokens(msgs) == (11 + 40) // 4


def test_fmt_bytes_units():
    assert _fmt_bytes(0) == "0.0 B"
    assert _fmt_bytes(2048).endswith(" KB")
    assert _fmt_bytes(5 * 1024 * 1024).endswith(" MB")
    assert _fmt_bytes(3 * 1024 * 1024 * 1024).endswith(" GB")


def test_fmt_duration_simple():
    assert _fmt_duration(45) == "0m"
    assert _fmt_duration(60) == "1m"
    assert _fmt_duration(3700).endswith("1m")
    # days appear once we cross 86400s
    assert _fmt_duration(2 * 86400 + 3 * 3600 + 4 * 60).startswith("2d")
