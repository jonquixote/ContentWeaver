from __future__ import annotations

import os
from pathlib import Path


def cache_dir() -> Path:
    return Path(os.getenv("CINEMA_CACHE_DIR", "/tmp/cw-cinema-cache"))
