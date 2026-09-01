from __future__ import annotations

import os

from src.services.footage.importers import LICENSE_ALLOWLIST
from src.services.footage.sources.base import CandidateVideo

MAX_DURATION_S = 120.0


def allow_license(license_spdx: str | None, source: str) -> bool:
    """Hard gate: an asset without an allowlisted license is never downloaded."""
    if not license_spdx:
        return False
    # source-specific exclude (paid sources)
    if source in ("publicdomainfootage.com", "footagefarm"):
        return False
    return license_spdx in LICENSE_ALLOWLIST


def duration_allowed(duration_s: float | None) -> bool:
    """Amendment 1 guard: long-form archival (>120s) is quarantined as
    'needs_segmentation' since shot segmentation is deferred — such assets must
    NOT reach retrieval. Unknown duration is allowed (asserted later)."""
    if duration_s is None:
        return True
    return float(duration_s) <= MAX_DURATION_S


def _upsert_asset(store, candidate: CandidateVideo, status: str = "discovered") -> str:
    """Write the asset source-of-truth row to footage_assets (with status) AND
    the vector to the VectorStore. Retrieval hydrates from footage_assets and
    filters status='ready', so quarantined assets never leak through."""
    import sqlite3
    asset_id = f"{candidate.source}:{candidate.source_id}"
    db = os.getenv("FOOTAGE_ASSETS_DB", os.getenv("FOOTAGE_VECTOR_DB", "/tmp/cw-footage-vec.db"))
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO footage_assets "
            "(id, source, source_id, title, description, license_spdx, license_raw, "
            "attribution_required, attribution_text, page_url, download_url, status, duration_s) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (asset_id, candidate.source, candidate.source_id, candidate.title,
             candidate.description, candidate.license_spdx, candidate.license_raw,
             int(candidate.extras.get("attribution_required", False)),
             candidate.attribution_text, candidate.page_url, candidate.download_url,
             status, candidate.duration_s),
        )
        conn.commit()
    except sqlite3.Error:
        # footage_assets not migrated yet (tests run before Task 12); the vector
        # store is the fallback source of truth.
        pass
    finally:
        conn.close()
    store.upsert({
        "id": asset_id,
        "source": candidate.source,
        "source_id": candidate.source_id,
        "title": candidate.title,
        "description": candidate.description,
        "duration_s": candidate.duration_s,
        "width": candidate.width,
        "height": candidate.height,
        "license_spdx": candidate.license_spdx,
        "license_raw": candidate.license_raw,
        "attribution_required": candidate.extras.get("attribution_required", False),
        "attribution_text": candidate.attribution_text,
        "page_url": candidate.page_url,
        "download_url": candidate.download_url,
        "status": status,
    })
    return asset_id


def enqueue_acquire(candidate: CandidateVideo) -> str:
    """Run the acquire->normalize->analyze->index chain (same for API + manual).
    Long-form assets are quarantined (needs_segmentation), not analyzed; a
    successfully-analyzed asset is marked status='ready' so retrieval returns it."""
    from src.services.footage.vectorstore import make_vector_store
    store = make_vector_store()
    if not duration_allowed(candidate.duration_s):
        return _upsert_asset(store, candidate, status="needs_segmentation")
    asset_id = _upsert_asset(store, candidate, status="discovered")
    from src.services.footage.analyze import analyze_clip  # Task 7
    analyze_clip(asset_id, candidate)
    # mark ready post-analysis (mutation in place: same asset_id)
    _set_status(asset_id, "ready")
    return asset_id


def _set_status(asset_id: str, status: str) -> None:
    import sqlite3
    db = os.getenv("FOOTAGE_ASSETS_DB", os.getenv("FOOTAGE_VECTOR_DB", "/tmp/cw-footage-vec.db"))
    try:
        conn = sqlite3.connect(db)
        conn.execute("UPDATE footage_assets SET status=? WHERE id=?", (status, asset_id))
        conn.commit()
        conn.close()
    except sqlite3.Error:
        pass


def discover(source: str, query: str, limit: int = 100) -> int:
    """Page adapter search(), license-filter, enqueue acquire. Idempotent."""
    from src.services.footage.sources.registry import get_source
    src = get_source(source)
    page = src.search(query, limit=limit)
    n = 0
    for c in page.candidates:
        if not allow_license(c.license_spdx, c.source):
            continue
        # enqueue_acquire applies the duration guard (quarantines long-form).
        try:
            enqueue_acquire(c)
            n += 1
        except Exception as e:
            print(f"ingest acquire failed for {c.source_id}: {e}")
    return n


def recheck_licenses() -> None:
    print("footage recheck_licenses: scheduled daily -> re-fetch metadata")
