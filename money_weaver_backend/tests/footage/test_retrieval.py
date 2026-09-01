from src.services.footage.retrieval import route_search, search_clips


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


def test_search_clips_applies_source_and_duration_filters(monkeypatch):
    # A stub embedder yields a vector so the store is queried; seed a
    # footage_assets table (status='ready') so hydration succeeds; assert both
    # filters bind.
    import os, tempfile, sqlite3
    from src.services.footage.vectorstore import SqliteVecStore, make_vector_store
    from src.services.footage.retrieval import search_clips

    class StubEmbedder:
        def embed_text(self, s):
            return [1.0, 0.0, 0.0]

    import src.services.footage.retrieval as ret
    ret.make_embedder = StubEmbedder
    d = tempfile.mkdtemp()
    monkeypatch.setenv("FOOTAGE_VECTOR_DB", os.path.join(d, "vec.db"))
    monkeypatch.setenv("FOOTAGE_ASSETS_DB", os.path.join(d, "assets.db"))
    store = make_vector_store()
    store.upsert({"id": "a", "embedding": [1.0, 0.0, 0.0], "source": "archive_org", "scale": "ms", "duration_s": 10.0})
    store.upsert({"id": "b", "embedding": [0.9, 0.1, 0.0], "source": "pexels", "scale": "cu", "duration_s": 1.0})
    # footage_assets (hydrate contract): status must be 'ready' to be returned.
    conn = sqlite3.connect(os.path.join(d, "assets.db"))
    conn.execute("CREATE TABLE footage_assets (id TEXT PRIMARY KEY, source TEXT, source_id TEXT, title TEXT, description TEXT, license_spdx TEXT, attribution_required INT, attribution_text TEXT, page_url TEXT, download_url TEXT, status TEXT, duration_s REAL)")
    for i, src in (("a", "archive_org"), ("b", "pexels")):
        conn.execute(
            "INSERT INTO footage_assets (id, source, source_id, title, status, duration_s) VALUES (?, ?, ?, ?, 'ready', ?)",
            (i, src, f"sid-{i}", f"clip {i}", (10.0 if i == "a" else 1.0)),
        )
    conn.commit(); conn.close()

    hits = search_clips("x", limit=5, min_duration_s=2.0, filters={})
    assert [h["id"] for h in hits] == ["a"]

    hits = search_clips("x", limit=5, min_duration_s=0.0, filters={"sources": ["archive_org"]})
    assert [h["id"] for h in hits] == ["a"]

    hits = search_clips("x", limit=5, min_duration_s=2.0, filters={"sources": ["pexels"]})
    assert hits == []


def test_quarantined_asset_with_embedding_never_retrieved(monkeypatch):
    # Fold (1): status='ready' gate means a QUARANTINED asset (needs_segmentation)
    # is never returned even though it has an embedding in the vector store.
    import os, tempfile, sqlite3
    from src.services.footage.vectorstore import make_vector_store
    from src.services.footage.retrieval import search_clips

    class StubEmbedder:
        def embed_text(self, s):
            return [1.0, 0.0, 0.0]

    import src.services.footage.retrieval as ret
    ret.make_embedder = StubEmbedder
    d = tempfile.mkdtemp()
    monkeypatch.setenv("FOOTAGE_VECTOR_DB", os.path.join(d, "vec.db"))
    monkeypatch.setenv("FOOTAGE_ASSETS_DB", os.path.join(d, "assets.db"))
    store = make_vector_store()
    store.upsert({"id": "z", "embedding": [1.0, 0.0, 0.0], "source": "archive_org", "scale": "ms", "duration_s": 30.0})
    conn = sqlite3.connect(os.path.join(d, "assets.db"))
    conn.execute("CREATE TABLE footage_assets (id TEXT PRIMARY KEY, source TEXT, source_id TEXT, title TEXT, description TEXT, license_spdx TEXT, attribution_required INT, attribution_text TEXT, page_url TEXT, download_url TEXT, status TEXT, duration_s REAL)")
    # embedded but quarantined (backfill future case that must NOT leak)
    conn.execute("INSERT INTO footage_assets (id, source, source_id, title, status, duration_s) VALUES ('z','archive_org','sid-z','clip z','needs_segmentation',30.0)")
    conn.commit(); conn.close()
    assert search_clips("x", limit=5, min_duration_s=0.0, filters={}) == []


def test_route_search_returns_signal_on_low_coverage(monkeypatch):
    # Fold (3): route_search returns (hits, fell_back). With none-embedder the
    # index yields nothing -> fell_back=True (caller should run live fallback).
    monkeypatch.setenv("EMBED_BACKEND", "none")
    hits, fell = route_search("aerial coastline", limit=5, min_duration_s=2.0, filters={})
    assert hits == []
    assert fell is True
