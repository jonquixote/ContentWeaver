from __future__ import annotations

import os
import sqlite3

from src.services.footage.embedder import make_embedder
from src.services.footage.vectorstore import make_vector_store


def _assets_db() -> str:
    return os.getenv("FOOTAGE_ASSETS_DB", os.getenv("FOOTAGE_VECTOR_DB", "/tmp/cw-footage-vec.db"))


def _hydrate(rows: list[dict]) -> list[dict]:
    """Join skinny {id, score, duration_s, source} hits against footage_assets
    for download_url / credit / caption. Filters to status='ready' so a
    quarantined asset (needs_segmentation) is never returned, even if it has an
    embedding."""
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    conn = sqlite3.connect(_assets_db())
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" for _ in ids)
        q = (f"SELECT id, source, source_id, title, description, license_spdx, "
             f"attribution_required, attribution_text, page_url, download_url, "
             f"status, duration_s FROM footage_assets WHERE id IN ({placeholders})")
        by_id = {r["id"]: dict(r) for r in conn.execute(q, ids).fetchall()}
    except sqlite3.Error as e:
        raise RuntimeError(f"footage_assets missing/read-failed: {e} "
                           "-- run the Task 12 migration / set FOOTAGE_ASSETS_DB") from e
    finally:
        conn.close()
    out = []
    for r in rows:
        asset = by_id.get(r["id"])
        if not asset:
            continue
        if asset.get("status") != "ready":
            continue  # quarantined / unanalysed: never retrieved
        out.append({**r, "caption": asset.get("title") or asset.get("description"),
                    "download_url": asset.get("download_url"),
                    "attribution_required": bool(asset.get("attribution_required")),
                    "attribution_text": asset.get("attribution_text")})
    return out


def search_clips(
    text: str,
    limit: int = 12,
    min_duration_s: float = 2.0,
    filters: dict | None = None,
) -> list[dict]:
    """Index-first retrieval (metadata-semantic v1). Returns hydrated rows
    (joined from footage_assets), filtered to status='ready'.

    With EMBED_BACKEND=none or an empty index -> [] (caller falls back to live).
    """
    filters = filters or {}
    embedder = make_embedder()
    vector = embedder.embed_text(text)
    if not vector:
        return []
    store = make_vector_store()
    hits = store.query(vector, k=limit, filters=filters)
    source_filter = filters.get("sources")
    if source_filter:
        hits = [h for h in hits if h.get("source") in source_filter]
    hits = [h for h in hits if h.get("duration_s") is None or h.get("duration_s", 0) >= min_duration_s]
    return _hydrate(hits[:limit])


def route_search(
    text: str,
    limit: int = 12,
    min_duration_s: float = 2.0,
    filters: dict | None = None,
) -> tuple[list[dict], bool]:
    """Index-first routing. Returns (hits, fell_back): fell_back=True when the
    index hit-count is below FOOTAGE_LIVE_FALLBACK_THRESHOLD, signalling the
    caller to run the live-provider fallback. The live call itself is the
    Phase-2 stock-service swap (shape-only here)."""
    hits = search_clips(text, limit, min_duration_s, filters)
    coverage_threshold = int(os.getenv("FOOTAGE_LIVE_FALLBACK_THRESHOLD", "3"))
    fell_back = len(hits) < coverage_threshold
    return hits, fell_back
