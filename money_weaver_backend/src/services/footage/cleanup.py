from __future__ import annotations

import os
import time

MEDIA_EXT = (".mp4", ".mp3", ".wav", ".mov", ".m4a")


def purge_stale_media(work_dir: str, older_than_hours: float) -> int:
    """Delete video/audio files older than `older_than_hours` (default from
    FOOTAGE_DISK_RETENTION_H, default 1). Returns count removed. Non-media files
    are never touched."""
    cutoff = time.time() - older_than_hours * 3600
    removed = 0
    for name in os.listdir(work_dir):
        if not name.lower().endswith(MEDIA_EXT):
            continue
        p = os.path.join(work_dir, name)
        try:
            if os.path.getmtime(p) < cutoff:
                os.remove(p)
                removed += 1
        except OSError:
            continue
    return removed


def run_disk_cleanup() -> int:
    hours = float(os.getenv("FOOTAGE_DISK_RETENTION_H", "1"))
    work_dir = os.getenv("FOOTAGE_WORK_DIR", "work")
    return purge_stale_media(work_dir, hours)
