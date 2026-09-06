import os
from src.services.footage.acquire import evict_lru, master_path_for, store_usage_bytes


def test_master_path_layout(tmp_path):
    p = master_path_for("archive_org", "abc123", root=str(tmp_path))
    assert p.startswith(str(tmp_path))
    assert "archive_org" in p and "abc123" in p


def test_store_usage_sums_masters(tmp_path):
    d = tmp_path / "archive_org" / "x"
    d.mkdir(parents=True)
    (d / "master.mp4").write_bytes(b"0" * 100)
    assert store_usage_bytes(str(tmp_path)) == 100


def test_evict_lru_oldest_first_under_budget(tmp_path):
    import time
    for name, age_s, size in (("a", 7200, 60), ("b", 3600, 60), ("c", 60, 60)):
        d = tmp_path / "s" / name
        d.mkdir(parents=True)
        f = d / "master.mp4"
        f.write_bytes(b"0" * size)
        old = time.time() - age_s
        os.utime(f, (old, old))
    evicted = evict_lru(str(tmp_path), 120)
    assert evicted == ["s/a"]  # oldest first, stops once under budget
    assert os.path.exists(tmp_path / "s" / "b" / "master.mp4")


def test_ensure_master_refuses_pexels_pixabay_storage(tmp_path, monkeypatch):
    # License posture: Pexels/Pixabay are NEVER written to the master store.
    monkeypatch.setenv("FOOTAGE_MASTER_DIR", str(tmp_path))
    from src.services.footage.acquire import ensure_master
    from src.services.footage.sources.base import CandidateVideo
    for source in ("pexels", "pixabay"):
        c = CandidateVideo(source=source, source_id="1", title="t", description=None,
                           tags=[], subjects=[], creator=None, published_at=None,
                           duration_s=10, width=1920, height=1080,
                           download_url="https://example.com/x.mp4", page_url="p",
                           license_spdx="CC0-1.0", license_raw=None, attribution_text=None)
        path, duration = ensure_master(c, root=str(tmp_path))
        assert path is None
        # duration passes through even when the path is refused (hot-link serve
        # uses the candidate's own duration downstream)
        assert duration == 10
    assert list(tmp_path.rglob("master.*")) == []


def test_ensure_master_idempotent_resume_safe(tmp_path, monkeypatch):
    # Second call for the same asset is a no-op returning the same path.
    monkeypatch.setenv("FOOTAGE_MASTER_DIR", str(tmp_path))
    from src.services.footage.acquire import ensure_master
    from src.services.footage.sources.base import CandidateVideo
    c = CandidateVideo(source="archive_org", source_id="abc", title="t", description=None,
                       tags=[], subjects=[], creator=None, published_at=None,
                       duration_s=10, width=640, height=480,
                       download_url="https://example.com/a.mp4", page_url="p",
                       license_spdx="public-domain", license_raw=None, attribution_text=None)
    import src.services.footage.acquire as acq
    monkeypatch.setattr(acq, "_fetch_to_temp", lambda url, tmp, have=0: open(tmp, "wb").write(b"0" * 10) or tmp)
    # stub _probe_duration: 10 zero bytes are not a real video in production,
    # but unit scope is idempotency mechanics, so report a probed duration
    monkeypatch.setattr(acq, "_probe_duration", lambda path: 10.0)
    p1, d1 = ensure_master(c, root=str(tmp_path))
    p2, d2 = ensure_master(c, root=str(tmp_path))
    assert p1 == p2 and p1 is not None
    assert open(p1, "rb").read() == b"0" * 10  # not re-downloaded/corrupted
    # probed-true duration preferred over the candidate's
    assert d1 == 10.0 and d2 == 10.0


def test_ensure_master_rejects_unprobable_download(tmp_path, monkeypatch):
    # Garbage bytes (e.g. archive.org 200-OK HTML): probe fails -> delete tmp,
    # return (None, candidate duration), never promote. A retry re-attempts the
    # fetch instead of trusting an invalid master.
    monkeypatch.setenv("FOOTAGE_MASTER_DIR", str(tmp_path))
    from src.services.footage.acquire import ensure_master
    from src.services.footage.sources.base import CandidateVideo
    c = CandidateVideo(source="archive_org", source_id="bad", title="t", description=None,
                       tags=[], subjects=[], creator=None, published_at=None,
                       duration_s=None, width=640, height=480,
                       download_url="https://example.com/a.mp4", page_url="p",
                       license_spdx="public-domain", license_raw=None, attribution_text=None)
    import src.services.footage.acquire as acq
    monkeypatch.setattr(acq, "_fetch_to_temp", lambda url, tmp, have=0: open(tmp, "wb").write(b"<html>nope</html>") or tmp)
    monkeypatch.setattr(acq, "_probe_duration", lambda path: None)  # unprobable
    p1, d1 = ensure_master(c, root=str(tmp_path))
    assert p1 is None
    assert d1 is None  # candidate had none either: genuinely unknown, never fabricated
    assert list(tmp_path.rglob("master.*")) == []  # nothing promoted
    # retry re-attempts (no poisoned master blocking the idempotent path)
    p2, d2 = ensure_master(c, root=str(tmp_path))
    assert p2 is None and d2 is None
