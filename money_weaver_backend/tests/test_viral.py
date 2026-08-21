"""Tests for viral moment detection (Task 7).

All heavy deps (faster_whisper, scenedetect, google-genai) are mocked or
absent from this venv — no network, no models, no real ffmpeg.
"""
from unittest import mock

import pytest

from src.services.video import viral_detector


# ---------------------------------------------------------------------------
# detect_viral_moments — happy path with all stages mocked
# ---------------------------------------------------------------------------

def test_detect_mocked(monkeypatch):
    monkeypatch.setattr(
        "src.services.video.viral_detector.transcribe",
        lambda p: [{"word": "wow", "start": 0, "end": 1}])
    monkeypatch.setattr(
        "src.services.video.viral_detector.detect_scenes",
        lambda p: [(0, 5), (5, 10)])
    monkeypatch.setattr(
        "src.services.video.viral_detector.call_gemini",
        lambda t, s: [{"start": 0, "end": 5, "score": 0.9, "hook": "Wow"}])
    clips = viral_detector.detect_viral_moments("/tmp/v.mp4", count=1)
    assert clips[0]["score"] == 0.9


def test_detect_passes_transcript_and_scenes_to_gemini(monkeypatch):
    seen = {}

    def fake_gemini(transcript, scenes):
        seen['transcript'] = transcript
        seen['scenes'] = scenes
        return [{"start": 0, "end": 15, "score": 0.8, "hook": "h"}]

    monkeypatch.setattr(viral_detector, "transcribe",
                        lambda p: [{"word": "hi", "start": 0, "end": 1}])
    monkeypatch.setattr(viral_detector, "detect_scenes", lambda p: [(0, 15)])
    monkeypatch.setattr(viral_detector, "call_gemini", fake_gemini)
    viral_detector.detect_viral_moments("/tmp/v.mp4")
    assert seen['transcript'] == [{"word": "hi", "start": 0, "end": 1}]
    assert seen['scenes'] == [(0, 15)]


def test_detect_respects_count(monkeypatch):
    moments = [{"start": i * 10, "end": i * 10 + 5, "score": 0.5, "hook": f"h{i}"}
               for i in range(10)]
    monkeypatch.setattr(viral_detector, "transcribe", lambda p: [])
    monkeypatch.setattr(viral_detector, "detect_scenes", lambda p: [])
    monkeypatch.setattr(viral_detector, "call_gemini", lambda t, s: moments)
    assert len(viral_detector.detect_viral_moments("/tmp/v.mp4", count=3)) == 3


# ---------------------------------------------------------------------------
# Fallbacks — never raise to the caller
# ---------------------------------------------------------------------------

def test_call_gemini_raises_without_key(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    with pytest.raises(RuntimeError):
        viral_detector.call_gemini([], [])


def test_missing_key_falls_back_to_scene_cuts(monkeypatch):
    """No GEMINI_API_KEY -> call_gemini raises -> scene cuts become clips."""
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    monkeypatch.setattr(viral_detector, "transcribe", lambda p: [])
    monkeypatch.setattr(viral_detector, "detect_scenes",
                        lambda p: [(0, 5), (5, 10)])
    clips = viral_detector.detect_viral_moments("/tmp/v.mp4", count=2)
    assert len(clips) == 2
    assert clips[0]["start"] == 0 and clips[0]["end"] == 5
    for clip in clips:
        assert set(clip) >= {"start", "end", "score", "hook"}


def test_gemini_failure_falls_back_to_scene_cuts(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key')
    monkeypatch.setattr(viral_detector, "transcribe", lambda p: [])
    monkeypatch.setattr(viral_detector, "detect_scenes",
                        lambda p: [(10, 25), (30, 45)])
    monkeypatch.setattr(viral_detector, "call_gemini",
                        mock.Mock(side_effect=RuntimeError("api down")))
    clips = viral_detector.detect_viral_moments("/tmp/v.mp4", count=1)
    assert clips == [{"start": 10, "end": 25, "score": 0.0, "hook": ""}]


def test_total_failure_returns_empty_list(monkeypatch):
    """Even transcription failing must not raise — final fallback is []."""
    monkeypatch.setattr(viral_detector, "transcribe",
                        mock.Mock(side_effect=OSError("no file")))
    monkeypatch.setattr(viral_detector, "detect_scenes",
                        mock.Mock(side_effect=OSError("no file")))
    assert viral_detector.detect_viral_moments("/tmp/missing.mp4") == []


# ---------------------------------------------------------------------------
# Stage stubs
# ---------------------------------------------------------------------------

def test_detect_scenes_stub_returns_list():
    # Stub until the scenedetect port lands; must not raise on any input.
    assert viral_detector.detect_scenes("/nonexistent.mp4") == []


# ---------------------------------------------------------------------------
# Router POST /api/clips/detect
# ---------------------------------------------------------------------------

def _create_project(client, headers):
    r = client.post('/api/projects', json={'title': 'viral project'}, headers=headers)
    assert r.status_code == 201
    return r.json()['id']


def test_clips_detect_happy_path(client, auth_headers):
    pid = _create_project(client, auth_headers)
    from fastapi_app.routers import generation
    with mock.patch.object(generation.detect_viral_clips_task, 'delay',
                           return_value=mock.Mock(id='cel-viral-1')) as delay:
        r = client.post('/api/clips/detect',
                        json={'video_key': 'uploads/v.mp4', 'count': 3,
                              'project_id': pid},
                        headers=auth_headers)
    assert r.status_code == 202
    body = r.json()
    assert body['celery_task_id'] == 'cel-viral-1'
    assert body['project_id'] == pid
    assert delay.call_args.kwargs['count'] == 3


def test_clips_detect_requires_auth(client):
    r = client.post('/api/clips/detect', json={'video_key': 'v.mp4'})
    assert r.status_code == 401


def test_clips_detect_requires_video_key(client, auth_headers):
    assert client.post('/api/clips/detect', json={'count': 3},
                       headers=auth_headers).status_code == 400


def test_clips_detect_foreign_project_is_403(client, auth_headers):
    client.post('/api/auth/register', json={
        'email': 'viral-other@test.com', 'username': 'viralother',
        'password': 'password123'})
    other = client.post('/api/auth/login', json={
        'email': 'viral-other@test.com', 'password': 'password123'}).json()['token']
    other_headers = {'Authorization': f'Bearer {other}'}
    pid = _create_project(client, auth_headers)
    r = client.post('/api/clips/detect',
                    json={'video_key': 'v.mp4', 'project_id': pid},
                    headers=other_headers)
    assert r.status_code == 403


def test_clips_detect_nonexistent_project_is_404(client, auth_headers):
    r = client.post('/api/clips/detect',
                    json={'video_key': 'v.mp4', 'project_id': 9999},
                    headers=auth_headers)
    assert r.status_code == 404


def test_clips_detect_queue_unavailable_is_503(client, auth_headers):
    pid = _create_project(client, auth_headers)
    from fastapi_app.routers import generation
    with mock.patch.object(generation.detect_viral_clips_task, 'delay',
                           side_effect=RuntimeError('redis down')):
        r = client.post('/api/clips/detect',
                        json={'video_key': 'v.mp4', 'project_id': pid},
                        headers=auth_headers)
    assert r.status_code == 503
