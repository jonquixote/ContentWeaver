import pytest
from unittest.mock import patch, MagicMock


def test_surprise_enqueues_assembler(client, auth_headers):
    """Surprise endpoint should enqueue assembler task with generation_type='assembler'."""
    captured = {}

    def fake_delay(**kwargs):
        captured.update(kwargs)
        return type("T", (), {"id": "cel-1"})()

    def fake_generate_idea(seed=None, model=None, language="en", user_id=None):
        return {"title": "Surprise Title", "topic": "Space", "script": "SCENE 1..."}

    def fake_pick_model(user_id, prefs, task):
        return "openrouter/free"

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("fastapi_app.routers.generation.generate_assembler_video_task.delay", fake_delay)
    with patch("fastapi_app.routers.generation.llm_service.generate_idea", fake_generate_idea), \
         patch("fastapi_app.routers.generation.llm_service.pick_model", fake_pick_model):
        r = client.post("/api/generate/surprise", json={"seed": "space"}, headers=auth_headers)
        assert r.status_code == 202
        body = r.json()
        assert body["message"] == "Video generation started"
        assert body["generation_type"] == "assembler"
        assert "task_id" in body
        assert "celery_task_id" in body
        assert "project_id" in body
        assert "settings" in body
        assert captured.get("prompt")


def test_surprise_generation_type_set(client, auth_headers, db_session):
    """Surprise endpoint should set generation_type='assembler' on the task."""
    captured = {}

    def fake_delay(**kwargs):
        captured.update(kwargs)
        return type("T", (), {"id": "cel-1"})()

    def fake_generate_idea(seed=None, model=None, language="en", user_id=None):
        return {"title": "Surprise Title", "topic": "Space", "script": "SCENE 1..."}

    def fake_pick_model(user_id, prefs, task):
        return "openrouter/free"

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("fastapi_app.routers.generation.generate_assembler_video_task.delay", fake_delay)
    with patch("fastapi_app.routers.generation.llm_service.generate_idea", fake_generate_idea), \
         patch("fastapi_app.routers.generation.llm_service.pick_model", fake_pick_model):
        r = client.post("/api/generate/surprise", json={"seed": "space"}, headers=auth_headers)
        assert r.status_code == 202
        body = r.json()
        task_id = body["task_id"]
        # Verify the task record has generation_type='assembler'
        from src.models.task import Task
        task = db_session.get(Task, task_id)
        assert task is not None
        assert task.generation_type == "assembler"

def test_surprise_provider_failure_is_503(client, auth_headers):
    from fastapi_app.routers import generation as gen_mod

    def boom(*a, **k):
        raise RuntimeError('openrouter 401: missing key')

    with patch.object(gen_mod.llm_service, 'generate_idea', side_effect=boom):
        r = client.post('/api/generate/surprise?seed=1', headers=auth_headers)
    assert r.status_code == 503
    assert 'unavailable' in r.json()['error']
