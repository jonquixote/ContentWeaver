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
