"""Phase 6: provider credential resolution + admin constants (no DB)."""

from app.llm import MOCK_MODEL, PROVIDER_OF, provider_credentials
from app.routers.admin import AUTONOMY_LEVELS, KNOWN_PROVIDERS


def test_provider_of_mapping():
    assert PROVIDER_OF["gpt-4.1"] == "openai"
    assert PROVIDER_OF["claude-sonnet"] == "anthropic"
    assert PROVIDER_OF["deepseek-chat"] == "deepseek"


def test_mock_needs_no_credentials():
    assert provider_credentials(None, MOCK_MODEL) == {}


def test_env_fallback_when_no_db_and_no_key():
    # No DB session, no env key configured in test env -> empty.
    assert provider_credentials(None, "gpt-4.1") == {}


def test_admin_constants():
    assert KNOWN_PROVIDERS == ["openai", "anthropic", "deepseek"]
    assert "scoped_auto" in AUTONOMY_LEVELS
    assert "full_auto" in AUTONOMY_LEVELS
    assert "approve_required" in AUTONOMY_LEVELS
