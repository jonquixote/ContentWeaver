import os
import tempfile
import time

from src.services.footage.cleanup import purge_stale_media


def test_purge_removes_stale_only():
    tmp = tempfile.mkdtemp()
    old = os.path.join(tmp, "old.mp4")
    new = os.path.join(tmp, "new.mp3")
    open(old, "wb").write(b"a" * 4)
    open(new, "wb").write(b"b" * 4)
    past = time.time() - 7200
    os.utime(old, (past, past))
    removed = purge_stale_media(tmp, older_than_hours=1)
    assert removed == 1
    assert not os.path.exists(old)
    assert os.path.exists(new)


def test_purge_keeps_recent():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "fresh.mp4")
    open(p, "wb").write(b"c" * 4)
    assert purge_stale_media(tmp, older_than_hours=1) == 0
    assert os.path.exists(p)


def test_purge_ignores_non_media():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "notes.txt")
    open(p, "wb").write(b"x" * 4)
    assert purge_stale_media(tmp, older_than_hours=0) == 0  # non-media kept even if stale
    assert os.path.exists(p)
