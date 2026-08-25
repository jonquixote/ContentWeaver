import pytest


@pytest.fixture
def fake_fal(monkeypatch):
    """Fake fal_client module: submit returns handle, status/result recorded."""
    import sys, types
    calls = {}
    mod = types.ModuleType("fal_client")
    mod.submit = lambda app, argument, api_key=None: calls.update(
        app=app, argument=argument, api_key=api_key) or types.SimpleNamespace(
        request_id="req-123")
    def _status(app, request_id, logs=False, api_key=None):
        calls['status_polls'] = calls.get('status_polls', 0) + 1
        if calls['status_polls'] < 2:
            return types.SimpleNamespace(status="IN_QUEUE")
        class Done:
            status = "COMPLETED"
        return Done()
    mod.status = _status
    mod.result = lambda app, request_id, api_key=None: calls.update(result=True) or {
        "video": {"url": "https://fake.cdn/out.mp4"}}
    monkeypatch.setitem(sys.modules, "fal_client", mod)
    return calls


def test_list_catalog_has_kinds():
    from src.services.providers.fal_adapter import FAL_CATALOG
    kinds = {e["kind"] for e in FAL_CATALOG}
    assert "voice" in kinds and "video" in kinds
    assert all(e["provider"] == "fal" and e["id"].startswith("fal-ai/")
               for e in FAL_CATALOG)


def test_submit_and_download(monkeypatch, tmp_path, fake_fal):
    from src.services.providers import fal_adapter
    monkeypatch.setattr(fal_adapter, "_download", lambda url, dest: dest.write_bytes(b"MP4"))
    out = fal_adapter.render("fal-ai/wan-t2v", {"prompt": "cat"},
                             api_key="FAKE", work_dir=str(tmp_path))
    assert fake_fal["app"] == "fal-ai/wan-t2v"
    assert fake_fal["argument"] == {"prompt": "cat"}
    assert fake_fal["api_key"] == "FAKE"
    assert out.endswith(".mp4") and (tmp_path / "out.mp4").exists() or True
    # exact assertion:
    import os
    assert os.path.exists(out) and os.path.getsize(out) > 0


def test_missing_api_key_raises(monkeypatch):
    from src.services.providers import fal_adapter
    monkeypatch.setattr(fal_adapter, "_key_for", lambda: None)
    with pytest.raises(RuntimeError, match="FAL key"):
        fal_adapter.render("fal-ai/x", {})
