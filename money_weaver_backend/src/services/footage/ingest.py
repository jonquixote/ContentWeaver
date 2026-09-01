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
    store.upsert({
        "id": f"{candidate.source}:{candidate.source_id}",
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
    return f"{candidate.source}:{candidate.source_id}"


def enqueue_acquire(candidate: CandidateVideo) -> str:
    """Run the acquire->normalize->analyze->index chain (same for API + manual).
    Long-form assets are quarantined (needs_segmentation), not analyzed."""
    from src.services.footage.vectorstore import make_vector_store
    store = make_vector_store()
    if not duration_allowed(candidate.duration_s):
        return _upsert_asset(store, candidate, status="needs_segmentation")
    asset_id = _upsert_asset(store, candidate)
    from src.services.footage.analyze import analyze_clip  # Task 7
    analyze_clip(asset_id, candidate)
    return asset_id


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
