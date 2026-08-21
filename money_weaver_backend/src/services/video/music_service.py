"""Royalty-free music bed selection + ffmpeg ducking mix.

Music files are NOT committed to git (licensing). music/manifest.yaml maps
track files to moods; niches/*.yaml carry a `music:` mood key. Empty or
missing manifest => silent videos, exactly as before.
"""
import os
import random

import yaml

_MUSIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "music",
)
_MANIFEST_PATH = os.path.join(_MUSIC_DIR, "manifest.yaml")

_MOOD_ALIASES = {
    "energetic": {"energetic", "upbeat", "sport", "gaming"},
    "calm": {"calm", "neutral", "ambient"},
    "corporate": {"corporate", "business", "finance", "news", "education"},
}


def _load_tracks():
    try:
        with open(_MANIFEST_PATH) as fh:
            data = yaml.safe_load(fh) or {}
    except FileNotFoundError:
        return []
    return data.get("tracks") or []


def pick_music(niche, duration=None):
    """Return an absolute path to a music file matching the niche's mood, or None."""
    niche_profile = None
    try:
        from src.services.providers.niche_profile import load as load_niche
        niche_profile = load_niche(niche)
    except Exception:
        niche_profile = None
    mood = ((niche_profile or {}).get("music") or "neutral").lower()
    allowed = _MOOD_ALIASES.get(mood, {mood})
    candidates = []
    for t in _load_tracks():
        f = t.get("file")
        if not f:
            continue
        if str(t.get("mood", "")).lower() in allowed and \
                os.path.exists(os.path.join(_MUSIC_DIR, f)):
            candidates.append(os.path.join(_MUSIC_DIR, f))
    return random.choice(candidates) if candidates else None


def mix_voice_music(voice_path, music_path, out_path, music_volume=0.3):
    """Duck music under voice via sidechaincompress; returns the ffmpeg cmd list.

    Caller is responsible for subprocess.run(cmd, check=True).
    """
    filter_complex = (
        f"[1:a]volume={music_volume}[m];"
        f"[m]asplit=2[mus][sc];"
        f"[0:a][sc]sidechaincompress=threshold=0.05:ratio=10:attack=5:release=300[comp];"
        f"[comp][mus]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )
    return [
        "ffmpeg", "-y",
        "-i", voice_path,
        "-i", music_path,
        "-filter_complex", filter_complex,
        "-map", "[aout]",
        "-ac", "2",
        out_path,
    ]
