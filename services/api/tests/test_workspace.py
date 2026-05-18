"""Phase 2: steering-file parser unit tests (pure, no filesystem/DB)."""

from app.workspace import _parse_agents, _parse_model_profiles

AGENTS_MD = """
## main
Zweck:
Allgemeiner Firmenassistent.

Modellprofil:
default-balanced

Tools:
- search_vector
- read_memory

Autonomie:
low

---

## devops
Zweck:
Server.

Modellprofil:
strong-reasoning

Tools:
- shell_readonly

Autonomie:
admin-configurable

Approval erforderlich für:
- Neustart von Diensten
- Deployment
"""

MODELS_MD = """
## default-balanced
Zweck:
Normale Arbeit.

Provider:
- openai/gpt-4.1
- anthropic/claude-sonnet

## strong-reasoning
Provider:
- anthropic/claude-sonnet
- deepseek/deepseek-reasoner
"""


def test_parse_agents():
    agents = _parse_agents(AGENTS_MD)
    assert set(agents) == {"main", "devops"}
    assert agents["main"].model_profile == "default-balanced"
    assert agents["main"].autonomy == "low"
    assert "search_vector" in agents["main"].tools
    assert agents["devops"].model_profile == "strong-reasoning"
    assert "Deployment" in agents["devops"].approval_actions


def test_parse_model_profiles():
    profiles = _parse_model_profiles(MODELS_MD)
    assert set(profiles) == {"default-balanced", "strong-reasoning"}
    assert profiles["default-balanced"].providers == [
        "openai/gpt-4.1",
        "anthropic/claude-sonnet",
    ]


def test_resolve_models_falls_back_to_mock():
    from app.llm import MOCK_MODEL, resolve_models

    # No DB, no env keys configured -> only mock-echo is usable.
    out = resolve_models(["openai/gpt-4.1", "anthropic/claude-sonnet"], None)
    assert out[-1] == MOCK_MODEL
