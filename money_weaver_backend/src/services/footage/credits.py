from __future__ import annotations

from src.services.cinema.clip import ClipRecord


def credits_manifest(used_clips: list[ClipRecord]) -> list[dict]:
    """Collect attributions for every used shot that requires credit."""
    out = []
    for c in used_clips:
        if getattr(c, "attribution_required", False):
            out.append({
                "clip_id": c.clip_id,
                "provider": c.provider,
                "attribution_text": c.attribution_text or f"Source: {c.provider}",
            })
    return out


def credits_text(used_clips: list[ClipRecord]) -> str:
    """Human-readable credits block appended at render (credits card)."""
    rows = credits_manifest(used_clips)
    if not rows:
        return ""
    lines = ["Credits:"]
    for r in rows:
        lines.append(f"- {r['attribution_text']}")
    return "\n".join(lines)


def collect_render_credits(video_data: list[tuple]) -> str:
    """Build the credits block from the render's used-video list
    [(path, duration, metadata)]. Reads attribution_required/text out of each
    item's metadata dict (set by _index_clips_for_scene); missing keys default
    to no-credit. Never raises (returns "" on any failure) — never blocks."""
    from pydantic import ValidationError
    try:
        clips = []
        for item in video_data or []:
            meta = item[2] if len(item) > 2 and isinstance(item[2], dict) else {}
            try:
                clips.append(ClipRecord(
                    clip_id=str(meta.get("clip_id", "")),
                    provider=str(meta.get("source", "local")),
                    source_url=str(item[0]) if len(item) > 0 else "",
                    duration_s=float(item[1]) if len(item) > 1 else 5.0,
                    attribution_required=bool(meta.get("attribution_required", False)),
                    attribution_text=meta.get("attribution_text")))
            except (ValidationError, ValueError, TypeError):
                continue  # unknown source literal: skip item, keep the block
        return credits_text(clips)
    except Exception:
        return ""
