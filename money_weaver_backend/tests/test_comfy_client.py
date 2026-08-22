"""ComfyUI HTTP gateway unit tests — all network calls mocked.

Covers health(), queue_workflow(), poll_result(), get_view() plus the workflow
template renderer. No real httpx/websocket traffic ever leaves the test.
"""
import json

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
async def test_poll_result_error_status_raises_promptly():
    """status_str == 'error' must raise on the FIRST poll even when outputs
    are present — failed jobs fail fast instead of hanging out the timeout."""
    fake = {
        "abc": {
            "outputs": {"9": {"videos": [{"filename": "out.mp4"}]}},
            "status": {"status_str": "error"},
        }
    }
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = _http_response(json_data=fake)
        with pytest.raises(RuntimeError, match="ComfyUI execution failed"):
            await comfy_client.poll_result("abc", timeout=300)
    assert mock_get.call_count == 1  # raised before any retry/sleep cycle


@pytest.mark.asyncio
async def test_get_view_returns_bytes():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.return_value = _http_response(content=b"MP4BYTES")
        data = await comfy_client.get_view("out.mp4")
    assert data == b"MP4BYTES"


def test_load_workflow_returns_template_dict():
    wf = comfy_client.load_workflow()
    assert isinstance(wf, dict)
    # Real Wan2.2 graph: positive prompt lives in the CLIPTextEncode node
    assert any(
        node["class_type"] == "CLIPTextEncode"
        and node["inputs"].get("text") == "__PROMPT__"
        for node in wf.values()
    )


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


def test_render_workflow_substitutes_all_params():
    from src.services import comfy_client as cc

    template = {
        "1": {"class_type": "WanVideoTextEncode", "inputs": {"text": "__PROMPT__"}},
        "2": {"class_type": "EmptyHunyuanLatentVideo", "inputs": {"width": "__WIDTH__", "height": "__HEIGHT__"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": "__SEED__"}},
    }
    meta = {"params": {"prompt": "1", "width": "2", "height": "2", "seed": "3"}}

    wf = cc.render_workflow(template, prompt="a cat", width=480, height=832, seed=42, meta=meta)
    assert wf["1"]["inputs"]["text"] == "a cat"
    assert wf["2"]["inputs"]["width"] == 480
    assert wf["2"]["inputs"]["height"] == 832
    assert wf["3"]["inputs"]["seed"] == 42


def test_render_workflow_token_scan_without_meta():
    from src.services import comfy_client as cc

    template = {"1": {"class_type": "X", "inputs": {"text": "__PROMPT__"}}}
    wf = cc.render_workflow(template, prompt="p", width=None, height=None, seed=None)
    assert wf["1"]["inputs"]["text"] == "p"


def test_render_workflow_does_not_mutate_template():
    from src.services import comfy_client as cc
    template = {"1": {"class_type": "X", "inputs": {"text": "__PROMPT__"}}}
    snapshot = json.dumps(template)
    cc.render_workflow(template, prompt="p", width=1, height=1, seed=1)
    assert json.dumps(template) == snapshot

def test_template_name_for_model():
    from src.tasks.video_tasks import _template_name_for_model
    assert _template_name_for_model("wan22-fp8") == "wan22_fp8_api.json"
    assert _template_name_for_model("WAN22-FP8-SCALED") == "wan22_fp8_api.json"
    assert _template_name_for_model(None) == "wan22_t2v_api.json"
    assert _template_name_for_model("wan22") == "wan22_t2v_api.json"


def test_enabled_generative_task_full_path(monkeypatch, client, auth_headers, db_session, tmp_path):
    """COMFY_ENABLED=true + healthy Comfy: task queues, polls, downloads,
    stores output locally + via storage.put_object, marks record completed.
    All network faked; Celery invoked synchronously via FakeTaskSelf."""
    import types
    from unittest import mock

    from src.models.task import Task
    from src.tasks import video_tasks as vt

    # -- DB rows: project + pending task record (route normally creates it) --
    r = client.post('/api/projects', json={'title': 'Gen e2e'},
                    headers=auth_headers)
    project_id = r.json()['id']

    with mock.patch.object(vt.generate_generative_video_task, 'delay',
                           return_value=mock.Mock(id='fake-celery-id')):
        task_id = client.post('/api/generate/generative',
                              json={'project_id': project_id, 'prompt': 'cat'},
                              headers=auth_headers).json()['task_id']

    # -- Flag + gateway mocks -------------------------------------------------
    monkeypatch.setenv('COMFY_ENABLED', 'true')
    monkeypatch.setattr(vt, 'FINAL_DIR', str(tmp_path))

    poll_calls = {'n': 0}

    async def fake_queue(wf, cid=None):
        return 'prompt-1'

    async def fake_poll(pid, timeout=300):
        # poll_result is the blocking loop inside comfy_client; the task calls
        # it once and expects a terminal payload back.
        poll_calls['n'] += 1
        return {'status': 'success',
                'outputs': {'9': {'gifs': [{'filename': 'wan_00001.mp4'}]}}}

    async def fake_view(fn):
        return b'MP4DATA'

    stored = {}
    fake_storage = mock.Mock()
    fake_storage.put_object = lambda key, data, content_type=None: stored.setdefault(key, data)

    pipeline = [
        mock.patch.object(vt.comfy_client, 'health', lambda: True),
        mock.patch.object(vt.comfy_client, 'queue_workflow', fake_queue),
        mock.patch.object(vt.comfy_client, 'poll_result', fake_poll),
        mock.patch.object(vt.comfy_client, 'get_view', fake_view),
        mock.patch.object(vt.llm_service, 'generate_script',
                          lambda *a, **k: 'enhanced prompt'),
        mock.patch.object(vt, 'get_storage', lambda: fake_storage),
    ]
    for p in pipeline:
        p.start()
    try:
        fake_self = types.SimpleNamespace(
            request=types.SimpleNamespace(id='fake-celery-id'))
        fake_self.update_state = lambda *a, **k: None
        vt.generate_generative_video_task.run.__func__(fake_self,
                                                       project_id=project_id,
                                                       prompt='cat')
    finally:
        for p in pipeline:
            p.stop()

    # -- Assertions -----------------------------------------------------------
    assert poll_calls['n'] == 1

    local_file = tmp_path / f'project_{project_id}_generative.mp4'
    assert local_file.exists() and local_file.read_bytes() == b'MP4DATA'

    expected_key = f'generative/{project_id}/project_{project_id}_generative.mp4'
    assert stored.get(expected_key) == b'MP4DATA'

    task = db_session.get(Task, task_id)
    assert task is not None and task.status == 'completed'
