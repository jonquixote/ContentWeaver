from __future__ import annotations

import os

from src.services.footage.embedder import make_embedder
from src.services.footage.vectorstore import make_vector_store


def search_clips(
    text: str,
    limit: int = 12,
    min_duration_s: float = 2.0,
    filters: dict | None = None,
) -> list[dict]:
    """Index-first retrieval (metadata-semantic v1: text-embed of
    title/description). Returns hydrated rows.

    With EMBED_BACKEND=none or an empty store -> [] (caller falls back to live).
    `filters` may carry `sources` (list[str]) — applied locally in v1.
    """
    filters = filters or {}
    embedder = make_embedder()
    vector = embedder.embed_text(text)
    store = make_vector_store()
    if not vector:
        return []
    hits = store.query(vector, k=limit, filters=filters)
    # v1 local filters the store does not express:
    source_filter = filters.get("sources")
    if source_filter:
        hits = [h for h in hits if h.get("source") in source_filter]
    hits = [h for h in hits if h.get("duration_s") is None or h.get("duration_s", 0) >= min_duration_s]
    return hits[:limit]


def route_search(
    text: str,
    limit: int = 12,
    min_duration_s: float = 2.0,
    filters: dict | None = None,
) -> list[dict]:
    """Index-first; caller falls back to live provider only when coverage <
    threshold. Returns the index hits; a live-fallback path is wired by the
    stock service swap (Phase 2)."""
    hits = search_clips(text, limit, min_duration_s, filters)
    coverage_threshold = int(os.getenv("FOOTAGE_LIVE_FALLBACK_THRESHOLD", "3"))
    if len(hits) >= coverage_threshold:
        return hits
    return hits
