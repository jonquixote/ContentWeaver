from src.services.video.stock_footage_service import _index_clips_for_scene, _serve_enabled


def test_serve_disabled_is_legacy(monkeypatch):
    # Flag off (or unset): serve gate closed.
    monkeypatch.delenv("FOOTAGE_SERVE_ENABLED", raising=False)
    assert _serve_enabled() is False


def test_serve_enabled_uses_index_hits(monkeypatch, tmp_path):
    monkeypatch.setenv("FOOTAGE_SERVE_ENABLED", "true")
    monkeypatch.setenv("FOOTAGE_MASTER_DIR", str(tmp_path))
    hits = [{"id": "archive_org:x", "source": "archive_org", "source_id": "x",
             "download_url": "https://example.com/x.mp4", "duration_s": 8.0,
             "license_spdx": "public-domain", "attribution_required": False,
             "attribution_text": None, "title": "x", "width": 640, "height": 480}]
    # Patch at the SOURCE modules: _index_clips_for_scene imports route_search
    # and ensure_master locally at call time.
    import src.services.footage.retrieval as ret
    monkeypatch.setattr(ret, "route_search", lambda *a, **k: (hits, False))
    import src.services.footage.acquire as acq
    monkeypatch.setattr(acq, "ensure_master",
                        lambda c, root=None: ("/tmp/master-x.mp4", 8.0))
    out = _index_clips_for_scene("comedian on stage", limit=4)
    assert out and out[0][0] == "/tmp/master-x.mp4"  # local master served
    assert out[0][1] == 8.0  # probed-true duration, never fabricated
    assert out[0][2]["from_index"] is True
    assert out[0][2]["duration_estimated"] is False


def test_serve_falls_back_live_when_index_thin(monkeypatch):
    monkeypatch.setenv("FOOTAGE_SERVE_ENABLED", "true")
    import src.services.footage.retrieval as ret
    monkeypatch.setattr(ret, "route_search", lambda *a, **k: ([], True))
    assert _index_clips_for_scene("comedian on stage", limit=4) == []
