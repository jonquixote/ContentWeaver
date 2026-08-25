import pytest


@pytest.fixture
def fake_fal(monkeypatch):
    """Fake fal_client module exposing a SyncClient class (fal-client >= 1.0
    moved auth to the client instance; module-level helpers lost api_key)."""
    import sys, types
    calls = {}
    mod = types.ModuleType("fal_client")

    class FakeSyncClient:
        def __init__(self, key=None, default_timeout=120.0):
            calls['key'] = key

        def submit(self, app, arguments):
            calls.update(app=app, argument=dict(arguments))
            return types.SimpleNamespace(request_id="req-123")

        def status(self, app, request_id):
            calls['status_polls'] = calls.get('status_polls', 0) + 1
            if calls['status_polls'] < 2:
                return types.SimpleNamespace(status="IN_QUEUE")
            return types.SimpleNamespace(status="COMPLETED")

        def result(self, app, request_id):
            calls['result_request_id'] = request_id
            return {"video": {"url": "https://fake.cdn/out.mp4"}}

    mod.SyncClient = FakeSyncClient
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
    assert fake_fal["key"] == "FAKE"
    assert fake_fal["result_request_id"] == "req-123"
    # exact assertion:
    import os
    assert os.path.exists(out) and os.path.getsize(out) > 0


def test_missing_api_key_raises(monkeypatch):
    from src.services.providers import fal_adapter
    monkeypatch.setattr(fal_adapter, "_key_for", lambda: None)
    with pytest.raises(RuntimeError, match="FAL key"):
        fal_adapter.render("fal-ai/x", {})
