"""ComfyUI HTTP gateway unit tests — all network calls mocked.

Covers health(), queue_workflow(), poll_result(), get_view() plus the workflow
template renderer. No real httpx/websocket traffic ever leaves the test.
"""
import httpx
import pytest
from unittest import mock
from unittest.mock import AsyncMock, patch

from src.services import comfy_client


def _http_response(status_code=200, json_data=None, content=b""):
    """Sync stand-in for an httpx.Response (patch() on async methods yields
    AsyncMock children whose .json() would return un-awaited coroutines)."""
    resp = mock.Mock()
    resp.status_code = status_code
    resp.json.return_value = json_data if json_data is not None else {}
    resp.content = content
    resp.raise_for_status = lambda: None
    return resp


@pytest.mark.asyncio
async def test_queue_and_poll_mocked():
    fake_workflow = {"1": {"class_type": "WanVideo"}}
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = _http_response(json_data={"prompt_id": "abc123"})
        with patch(
            "src.services.comfy_client.poll_result",
            new=AsyncMock(return_value={"status": "success", "path": "/tmp/out.mp4"}),
        ):
            pid = await comfy_client.queue_workflow(fake_workflow, "client1")
            assert pid == "abc123"


def test_health_mocked(monkeypatch):
    monkeypatch.setattr(
        comfy_client.httpx,
        "get",
        lambda *a, **k: type("R", (), {"status_code": 200})(),
    )
    assert comfy_client.health() is True


def test_health_false_when_down(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(comfy_client.httpx, "get", boom)
    assert comfy_client.health() is False


@pytest.mark.asyncio
async def test_queue_workflow_raises_on_error_response():
    with patch("httpx.AsyncClient.post") as mock_post:
        def fail(*a, **k):
            raise httpx.HTTPStatusError("boom", request=None, response=None)

        resp = _http_response()
        resp.raise_for_status = fail
        mock_post.return_value = resp
        with pytest.raises(httpx.HTTPStatusError):
            await comfy_client.queue_workflow({"1": {}}, "c")


@pytest.mark.asyncio
async def test_poll_result_returns_outputs():
    fake = {"abc": {"outputs": {"9": {"videos": [{"filename": "out.mp4", "type": "output"}]}}}}
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = _http_response(json_data=fake)
        out = await comfy_client.poll_result("abc", timeout=4)
    assert out["status"] == "success"
    assert out["outputs"]["9"]["videos"][0]["filename"] == "out.mp4"


@pytest.mark.asyncio
async def test_poll_result_times_out():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = _http_response(json_data={"abc": {}})
        with pytest.raises(TimeoutError):
            await comfy_client.poll_result("abc", timeout=2)


@pytest.mark.asyncio
async def test_get_view_returns_bytes():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = _http_response(content=b"MP4BYTES")
        data = await comfy_client.get_view("out.mp4")
    assert data == b"MP4BYTES"


def test_load_workflow_returns_template_dict():
    wf = comfy_client.load_workflow()
    assert isinstance(wf, dict)
    assert wf["1"]["class_type"] == "WanImageToVideo"


def test_render_workflow_injects_prompt_preserves_defaults():
    template = {
        "1": {
            "class_type": "WanImageToVideo",
            "inputs": {"prompt": "__PROMPT__", "width": 832, "height": 480},
        }
    }
    wf = comfy_client.render_workflow(template, "a cinematic ocean shot")
    assert wf["1"]["inputs"]["prompt"] == "a cinematic ocean shot"
    assert wf["1"]["inputs"]["width"] == 832
    assert wf["1"]["inputs"]["height"] == 480
    assert template["1"]["inputs"]["prompt"] == "__PROMPT__"  # original untouched