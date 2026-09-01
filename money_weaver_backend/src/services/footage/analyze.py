from __future__ import annotations

import os

from src.services.footage.embedder import make_embedder
from src.services.footage.sources.base import CandidateVideo
from src.services.cinema.clip import ClipRecord
from src.services.cinema.types import CameraMove, ShotScale


def _keyframe(candidate: CandidateVideo) -> str | None:
    # In production ffmpeg extracts proxy -> keyframe. USE_SCENEDETECT off ->
    # one clip per asset. Returns None for http URLs (no local frame) — the
    # attributes degrade to None (neutral).
    p = candidate.download_url
    if p.startswith("http"):
        return None
    return p if os.path.exists(p) else None


def extract_scale(_keyframe_path: str | None) -> ShotScale | None:
    # Face/person bbox area heuristic (deferred, Phase 2). None -> neutral.
    return None


def extract_move(_proxy_path: str | None) -> CameraMove | None:
    # Sparse optical flow classification (deferred, Phase 2). None -> neutral.
    return None


def motion_energy(_proxy_path: str | None) -> float | None:
    return None


def palette_luma(_keyframe_path: str | None) -> tuple[list[str], float | None]:
    return ([], None)


def analyze_clip(asset_id: str, candidate: CandidateVideo) -> list[ClipRecord]:
    embedder = make_embedder()
    kf = _keyframe(candidate)
    scale = extract_scale(kf)
    move = extract_move(kf)
    energy = motion_energy(kf)
    pal, luma = palette_luma(kf)
    emb = embedder.embed_text(candidate.title or candidate.description or "")
    provider = candidate.source if candidate.source in ("pexels", "pixabay", "local", "generative") else "local"
    return [
        ClipRecord(
            clip_id=f"{candidate.source}:{candidate.source_id}:shot0",
            provider=provider,
            source_url=candidate.download_url,
            local_path=candidate.download_url if not candidate.download_url.startswith("http") else None,
            duration_s=candidate.duration_s or 5.0,
            width=candidate.width,
            height=candidate.height,
            embedding=emb or None,
            caption=candidate.title,
            scale=scale,
            move=move,
            palette=pal,
            luminance=luma,
            motion_energy=energy,
            faces=0,
            average_hash=None,
            attribution_required=candidate.extras.get("attribution_required", False),
            attribution_text=candidate.attribution_text,
        )
    ]
