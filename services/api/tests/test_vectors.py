"""Phase 3: embedding determinism + collection naming (no infra)."""

from app.vectors import allowed_visibilities, collection_for, embed_text


def test_embed_deterministic_and_normalized():
    a = embed_text("Tessa ingests documents", 64)
    b = embed_text("Tessa ingests documents", 64)
    assert a == b  # deterministic -> worker & API agree
    assert len(a) == 64
    norm = sum(x * x for x in a) ** 0.5
    assert abs(norm - 1.0) < 1e-6
    assert embed_text("different text", 64) != a


def test_collection_for():
    assert collection_for("company-default") == "tessa_company_default"
    assert collection_for("Team A/1") == "tessa_team_a_1"


def test_visibility_by_role():
    assert "admin" in allowed_visibilities("superadmin")
    assert "admin" not in allowed_visibilities("user")
    assert "workspace" in allowed_visibilities("restricted")
