"""fal.ai voice/video generation adapter (fal-client, Apache-2.0).

Optional dependency: pip install fal-client. Keys stored per-user via the
ApiKey table (provider='fal'), decrypted by callers; env FAL_KEY as fallback.
"""
import os
import time
import uuid
from pathlib import Path


FAL_CATALOG = [
    {"id": "fal-ai/wan-t2v", "provider": "fal", "kind": "video",
     "display_name": "Wan 2.2 T2V (fal)", "free": False},
    {"id": "fal-ai/minimax/video-01", "provider": "fal", "kind": "video",
     "display_name": "MiniMax Video 01 (fal)", "free": False},
    {"id": "fal-ai/kokoro-tts", "provider": "fal", "kind": "voice",
     "display_name": "Kokoro TTS (fal)", "free": False},
]

_MEDIA_EXTS = (
    ".mp4", ".mov", ".webm", ".mkv",
    ".mp3", ".wav", ".ogg", ".m4a", ".flac",
)


def _key_for():
    return os.getenv("FAL_KEY")


def _download(url, dest_path):
    import httpx
    with httpx.stream("GET", url, timeout=300) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as fh:
            for chunk in r.iter_bytes():
                fh.write(chunk)
    return dest_path


def render(endpoint, arguments, api_key=None, work_dir="/tmp", timeout_s=600):
    """Submit to fal, poll until COMPLETED, download first media URL.

    Returns local file path. Raises RuntimeError on misconfig/timeout."""
    key = api_key or _key_for()
    if not key:
        raise RuntimeError("FAL key unavailable (save a fal API key or set FAL_KEY)")
    import fal_client
    handle = fal_client.submit(endpoint, arguments, api_key=key)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = fal_client.status(endpoint, handle.request_id, api_key=api_key)
        if getattr(status, "status", "") == "COMPLETED":
            break
        time.sleep(2)
    else:
        raise RuntimeError(f"fal render timed out after {timeout_s}s")
    result = fal_client.result(endpoint, handle.request_id, api_key=api_key)
    url = _extract_url(result)
    if not url:
        raise RuntimeError(f"no media url in fal result: {str(result)[:200]}")
    dest = Path(work_dir) / f"fal_{uuid.uuid4().hex}.mp4"
    _download(url, dest)
    return str(dest)


def _extract_url(result):
    """Walk nested result dicts/lists for the first video/audio media URL.

    Matches explicit content_type metadata when present; falls back to media
    file extensions because some fal queue responses omit content_type
    (see https://docs.fal.ai/model-endpoints/queue)."""
    def walk(node):
        if isinstance(node, dict):
            url = node.get("url")
            if url and (
                str(node.get("content_type", "")).startswith(("video/", "audio/"))
                or str(url).lower().split("?", 1)[0].endswith(_MEDIA_EXTS)
            ):
                return url
            for v in node.values():
                found = walk(v)
                if found:
                    return found
        elif isinstance(node, list):
            for v in node:
                found = walk(v)
                if found:
                    return found
        return None
    return walk(result)


def catalog_models():
    return [dict(e) for e in FAL_CATALOG]


# Self-register into the merged registry exactly once, surviving module
# reloads (fresh function objects break identity checks).
from src.services.providers.registry import EXTRA_CATALOG_SOURCES

if not any(getattr(s, "__module__", "") == __name__
           and getattr(s, "__name__", "") == "catalog_models"
           for s in EXTRA_CATALOG_SOURCES):
    EXTRA_CATALOG_SOURCES.append(catalog_models)
