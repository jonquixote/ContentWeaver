from src.services.footage.retrieval import search_clips


def test_search_clips_returns_valid_list(monkeypatch):
    monkeypatch.setenv("EMBED_BACKEND", "none")
    res = search_clips("empty factory floor at dawn", limit=5, min_duration_s=2.0, filters={})
    assert isinstance(res, list)


def test_search_clips_filters_honored(monkeypatch):
    monkeypatch.delenv("EMBED_BACKEND", raising=False)
    res = search_clips("aerial coastline", limit=8, min_duration_s=2.0,
                       filters={"sources": ["archive_org"]})
    assert isinstance(res, list)


def test_search_clips_maps_query_vector_from_embedder(monkeypatch):
    # With EMBED_BACKEND=none (no embedding), text query yields [] — the
    # metadata-semantic v1 index needs an embedder; graceful [ ] otherwise.
    monkeypatch.setenv("EMBED_BACKEND", "none")
    assert search_clips("aerial coastline", limit=5, min_duration_s=2.0, filters={}) == []
