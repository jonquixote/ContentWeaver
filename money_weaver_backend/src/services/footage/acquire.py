from __future__ import annotations

import os


def master_path_for(source: str, source_id: str, root: str | None = None) -> str:
    base = root or os.getenv("FOOTAGE_MASTER_DIR", "/tmp/cw-footage-masters")
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in source_id)
    return os.path.join(base, source, safe)


def _iter_masters(root: str) -> list[str]:
    out = []
    if not os.path.isdir(root):
        return out
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.startswith("master."):
                out.append(os.path.join(dirpath, fn))
    return out


def store_usage_bytes(root: str | None = None) -> int:
    base = root or os.getenv("FOOTAGE_MASTER_DIR", "/tmp/cw-footage-masters")
    total = 0
    for p in _iter_masters(base):
        try:
            total += os.path.getsize(p)
        except OSError:
            continue
    return total


def evict_lru(root: str | None = None, budget_bytes: int | None = None) -> list[str]:
    """Delete oldest-accessed masters until under budget. Returns evicted
    asset keys (source/source_id). Never evicts files younger than 1h.
    Masters are EXEMPT from the time-based retention purge; eviction here is
    size-driven only."""
    import time
    base = root or os.getenv("FOOTAGE_MASTER_DIR", "/tmp/cw-footage-masters")
    budget = budget_bytes if budget_bytes is not None else int(
        float(os.getenv("FOOTAGE_MASTER_BUDGET_GB", "25")) * 1024**3)
    now = time.time()
    cands = []
    for p in _iter_masters(base):
        try:
            st = os.stat(p)
        except OSError:
            continue
        if now - st.st_atime < 3600:
            continue  # young files exempt
        cands.append((st.st_atime, p))
    cands.sort()
    evicted = []
    usage = store_usage_bytes(base)
    for _, p in cands:
        if usage <= budget:
            break
        try:
            usage -= os.path.getsize(p)
            os.remove(p)
            rel = os.path.relpath(os.path.dirname(p), base)
            evicted.append(rel.replace(os.sep, "/"))
        except OSError:
            continue
    return evicted
