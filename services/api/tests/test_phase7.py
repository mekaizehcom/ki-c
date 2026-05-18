"""Phase 7: hybrid rerank + multi-workspace discovery."""

from app.vectors import hybrid_rerank


def test_lexical_overlap_promotes_relevant_chunk():
    hits = [
        {"text": "completely unrelated content about weather", "score": 0.9},
        {"text": "the tessa deployment uses docker compose and nginx", "score": 0.6},
    ]
    out = hybrid_rerank("how is tessa deployment with docker", hits, top_k=2)
    assert out[0]["text"].startswith("the tessa deployment")
    assert out[0]["score"] >= out[1]["score"]


def test_empty_query_returns_topk_unchanged():
    hits = [{"text": "a", "score": 0.5}, {"text": "b", "score": 0.4}]
    assert hybrid_rerank("", hits, top_k=1) == hits[:1]


def test_workspace_discovery_signature():
    # list_workspace_slugs always returns at least the default workspace.
    from app.workspace import list_workspace_slugs

    slugs = list_workspace_slugs()
    assert isinstance(slugs, list) and len(slugs) >= 1
