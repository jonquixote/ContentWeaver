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
