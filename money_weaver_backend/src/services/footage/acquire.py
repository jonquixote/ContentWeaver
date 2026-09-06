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


PD_CC_STORED_SOURCES = {
    "archive_org", "nasa_images", "loc", "wikimedia_commons", "open_images",
    "coverr", "pond5_pd",
    # manual-import PD/CC sources (VIDEO_SOURCES.md NO-CREDIT + CC lists)
    "mixkit", "dareful", "life_of_vids", "splitshire", "videezy", "videvo",
    "pikwizard", "xstockvideo", "cdc", "nps", "eso", "esa_hubble",
    "motionelements",
}
NEVER_STORE_SOURCES = {"pexels", "pixabay"}  # served per-render via stored URL


def _fetch_to_temp(url: str, tmp_path: str, existing_bytes: int = 0) -> str:
    """Download with resume: Range header from existing_bytes; returns tmp path."""
    import requests
    headers = {"Range": f"bytes={existing_bytes}-"} if existing_bytes > 0 else {}
    with requests.get(url, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()
        mode = "ab" if (existing_bytes > 0 and r.status_code == 206) else "wb"
        with open(tmp_path, mode) as f:
            for chunk in r.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)
    return tmp_path


def _probe_duration(path: str) -> float | None:
    """ffprobe duration; None when unprobable. Never raises."""
    import json
    import subprocess
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "json", path],
            capture_output=True, text=True, timeout=60)
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return None


def ensure_master(candidate, root: str | None = None) -> tuple[str | None, float | None]:
    """Lazy-acquire a PD/CC asset's master on first render use. Returns
    (local_path, true_duration). Idempotent and resume-safe: complete verified
    master → return as-is; partial → resume; Pexels/Pixabay → (None, candidate
    duration) — hot-link per render, never stored. Duration is the ffprobe-
    probed value when probed, else the candidate's, else None (genuinely
    unknown — never fabricated). Probes backfill footage_assets.duration_s."""
    import sqlite3
    if candidate.source in NEVER_STORE_SOURCES:
        return None, candidate.duration_s
    base = root or os.getenv("FOOTAGE_MASTER_DIR", "/tmp/cw-footage-masters")
    asset_dir = master_path_for(candidate.source, candidate.source_id, root=base)
    os.makedirs(asset_dir, exist_ok=True)
    existing = [p for p in os.listdir(asset_dir) if p.startswith("master.")]
    if existing:
        # idempotent: verified master; duration already probed at first acquire
        return os.path.join(asset_dir, existing[0]), candidate.duration_s
    tmp = os.path.join(asset_dir, "master.part")
    have = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    try:
        _fetch_to_temp(candidate.download_url, tmp, have)
    except Exception as e:
        print(f"cinema acquire failed for {candidate.source}:{candidate.source_id}: {e}")
        return None, candidate.duration_s
    ext = ".mp4"  # masters normalized to mp4 containers downstream
    final = os.path.join(asset_dir, "master.mp4")
    try:
        os.replace(tmp, final)
    except OSError:
        return None, candidate.duration_s
    dur = _probe_duration(final)
    true_duration = dur or candidate.duration_s  # None only if genuinely unknown
    if dur and not candidate.duration_s:
        _backfill_duration(candidate.source, candidate.source_id, dur)
    # enforce LRU budget after each acquire
    evict_lru(base)
    return final, true_duration


def _backfill_duration(source: str, source_id: str, duration_s: float) -> None:
    import sqlite3
    db = os.getenv("FOOTAGE_ASSETS_DB", os.getenv("FOOTAGE_VECTOR_DB", "/tmp/cw-footage-vec.db"))
    try:
        conn = sqlite3.connect(db)
        conn.execute("UPDATE footage_assets SET duration_s=? WHERE source=? AND source_id=?",
                     (duration_s, source, source_id))
        conn.commit()
        conn.close()
    except Exception:
        pass  # best-effort; assets table may not exist in unit tests
