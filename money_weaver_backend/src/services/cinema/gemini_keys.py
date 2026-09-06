from __future__ import annotations

import os
import time

# Per-key cooldown (seconds) after a 429, so a hot key is skipped briefly
# instead of being hammered on every call. Free-tier quota is per-day, but
# 429s also fire on per-minute bursts — a short cooldown lets the pool rotate
# across keys instead of failing over in lockstep.
COOLDOWN_S = int(os.getenv("GEMINI_KEY_COOLDOWN_S", "120"))

_cooling: dict[str, float] = {}


def _mask(key: str) -> str:
    return (key[:6] + "..." + key[-4:]) if len(key) > 10 else "***"


def get_keys() -> list[str]:
    """Ordered unique Gemini keys: primary + comma-separated fallbacks.
    More keys can be appended to GEMINI_API_KEY_FALLBACKS at any time."""
    primary = os.getenv("GEMINI_API_KEY") or ""
    fallbacks = [k.strip() for k in (os.getenv("GEMINI_API_KEY_FALLBACKS") or "").split(",") if k.strip()]
    keys = list(dict.fromkeys([primary] + fallbacks))
    return [k for k in keys if k]


def live_keys() -> list[str]:
    """Keys not currently in 429 cooldown, in priority order."""
    now = time.time()
    return [k for k in get_keys() if _cooling.get(k, 0) <= now]


def mark_exhausted(key: str, cooldown_s: int | None = None) -> None:
    """Record a 429 against a key so subsequent calls skip it briefly."""
    _cooling[key] = time.time() + (cooldown_s if cooldown_s is not None else COOLDOWN_S)


def mark_ok(key: str) -> None:
    """Clear any cooldown (a 200 proves the key has budget)."""
    _cooling.pop(key, None)


def reset_cooldowns() -> None:
    """Test helper: clear all cooldown state."""
    _cooling.clear()
