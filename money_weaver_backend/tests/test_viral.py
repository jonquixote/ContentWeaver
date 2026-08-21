"""Tests for viral moment detection (Task 7).

All heavy deps (faster_whisper, scenedetect, google-genai) are mocked or
absent from this venv — no network, no models, no real ffmpeg.
"""
import os
import subprocess
import sys
import tempfile
import types
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

def test_detect_scenes_unreadable_file_returns_list():
    # Real detector must degrade to [] on any unreadable input, never raise.
    assert viral_detector.detect_scenes("/nonexistent.mp4") == []


# ---------------------------------------------------------------------------
# Real scene detection — PySceneDetect ContentDetector (Phase D Task 4)
# ---------------------------------------------------------------------------

class _FakeFrameTime:
    def __init__(self, seconds):
        self._s = seconds

    def get_seconds(self):
        return self._s


def test_detect_scenes_runs_content_detector(monkeypatch):
    from src.services.video import viral_detector as vd

    class FakeVM:
        def __init__(self, paths):
            pass

        def set_downscale_factor(self):
            pass

        def start(self):
            pass

    class FakeSM:
        def __init__(self):
            self.added = []

        def add_detector(self, d):
            self.added.append(d)

        def detect_scenes(self, frame_source):
            pass

        def get_scene_list(self):
            return [
                (_FakeFrameTime(0.0), _FakeFrameTime(4.0)),
                (_FakeFrameTime(4.0), _FakeFrameTime(9.5)),
            ]

    calls = {}

    def fake_sm():
        calls['sm'] = FakeSM()
        return calls['sm']

    monkeypatch.setattr(vd, "_VideoManager", FakeVM)
    monkeypatch.setattr(vd, "_SceneManager", fake_sm)
    scenes = vd.detect_scenes("/tmp/fake.mp4")
    assert scenes == [(0.0, 4.0), (4.0, 9.5)]


def test_detect_scenes_merges_short_scenes(monkeypatch):
    from src.services.video import viral_detector as vd
    merged = vd._merge_short_scenes(
        [(0.0, 0.4), (0.4, 2.0), (2.0, 6.0)], min_len=1.0)
    assert merged[0][0] == 0.0 and merged[-1] == (2.0, 6.0)
    assert all((e - s) >= 1.0 or i == len(merged) - 1
               for i, (s, e) in enumerate(merged))


def test_no_key_fallback_now_returns_scene_cuts(monkeypatch):
    from src.services.video import viral_detector as vd
    monkeypatch.setattr(vd, "transcribe", lambda p: [])
    monkeypatch.setattr(vd, "detect_scenes",
                        lambda p: [(0.0, 5.0), (5.0, 10.0)])

    def gemini_fail(t, s):
        raise RuntimeError("no key")

    monkeypatch.setattr(vd, "call_gemini", gemini_fail)
    clips = vd.detect_viral_moments("/tmp/v.mp4", count=2)
    assert clips == [
        {"start": 0.0, "end": 5.0, "score": 0.0, "hook": ""},
        {"start": 5.0, "end": 10.0, "score": 0.0, "hook": ""},
    ]


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


# ---------------------------------------------------------------------------
# Malformed Gemini output -> scene-cut fallback (review fix)
# ---------------------------------------------------------------------------

def _install_fake_genai(monkeypatch, text):
    """Poison sys.modules with a google.genai stub whose model returns `text`."""
    fake_genai = types.ModuleType('google.genai')
    fake_client = mock.Mock()
    fake_client.models.generate_content.return_value.text = text
    fake_genai.Client = mock.Mock(return_value=fake_client)
    fake_google = types.ModuleType('google')
    fake_google.genai = fake_genai
    monkeypatch.setitem(sys.modules, 'google', fake_google)
    monkeypatch.setitem(sys.modules, 'google.genai', fake_genai)


def test_call_gemini_garbage_text_raises(monkeypatch):
    """No JSON array in the response text -> RuntimeError (caller falls back)."""
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key')
    _install_fake_genai(monkeypatch, "Sorry, I cannot help with that.")
    with pytest.raises(RuntimeError, match="no JSON array"):
        viral_detector.call_gemini([], [])


def test_call_gemini_truncated_json_raises(monkeypatch):
    """Array that never closes must not be silently accepted."""
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key')
    _install_fake_genai(monkeypatch, '[{"start": 0, "end": 5')
    with pytest.raises(RuntimeError):
        viral_detector.call_gemini([], [])


def test_call_gemini_parses_first_array_with_surrounding_prose(monkeypatch):
    """Regression: greedy regex swallowed prose between arrays; raw_decode
    must stop at the end of the first complete array."""
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key')
    _install_fake_genai(
        monkeypatch,
        'Here you go:\n[{"start": 1, "end": 4, "score": 0.7, "hook": "hi"}]'
        '\nHope that helps! [not json]')
    moments = viral_detector.call_gemini([], [])
    assert moments == [{"start": 1.0, "end": 4.0, "score": 0.7, "hook": "hi"}]


def test_malformed_gemini_text_falls_back_to_scene_cuts(monkeypatch):
    """Garbage Gemini text -> detect_viral_moments degrades, never raises."""
    monkeypatch.setenv('GEMINI_API_KEY', 'fake-key')
    monkeypatch.setattr(viral_detector, "transcribe", lambda p: [])
    monkeypatch.setattr(viral_detector, "detect_scenes",
                        lambda p: [(3, 9), (12, 20)])
    monkeypatch.setattr(viral_detector, "call_gemini",
                        mock.Mock(side_effect=RuntimeError("no JSON array")))
    clips = viral_detector.detect_viral_moments("/tmp/v.mp4", count=2)
    assert clips == [
        {"start": 3, "end": 9, "score": 0.0, "hook": ""},
        {"start": 12, "end": 20, "score": 0.0, "hook": ""},
    ]


# ---------------------------------------------------------------------------
# count validation — POST /api/clips/detect (review fix)
# ---------------------------------------------------------------------------

def test_coerce_clip_count_defaults_and_passthrough():
    from fastapi_app.routers.generation import _coerce_clip_count
    assert _coerce_clip_count(None) == 5
    assert _coerce_clip_count(3) == 3


@pytest.mark.parametrize("bad", [True, False, "3", 3.0, 0, -1])
def test_coerce_clip_count_rejects_invalid(bad):
    """bools are ints in Python — must be rejected explicitly; non-ints too."""
    from fastapi_app.routers.generation import _coerce_clip_count
    with pytest.raises(ValueError, match="positive integer"):
        _coerce_clip_count(bad)


def test_clips_detect_bool_count_rejected(client, auth_headers):
    """HTTP layer: a before-validator rejects bool-for-int (pydantic lax mode
    would otherwise coerce True -> 1); the app maps validation errors to 400.
    The router-level _coerce_clip_count guard stays as defense-in-depth."""
    pid = _create_project(client, auth_headers)
    r = client.post('/api/clips/detect',
                    json={'video_key': 'v.mp4', 'project_id': pid,
                          'count': True},
                    headers=auth_headers)
    assert r.status_code == 400
    assert 'positive integer' in r.json()['error']


# ---------------------------------------------------------------------------
# Celery task detect_viral_clips_task — ffmpeg failure path (review fix)
# ---------------------------------------------------------------------------

class _FakeTaskSelf:
    """Stand-in for the Celery task instance (no broker/backend required)."""

    def __init__(self, tid="fake-viral-celery-id"):
        self.request = types.SimpleNamespace(id=tid)

    def update_state(self, *args, **kwargs):
        pass


def test_viral_task_ffmpeg_failure_records_stderr(tmp_path, monkeypatch):
    """CalledProcessError from ffmpeg -> failed task record whose error
    message contains the captured stderr snippet; task fails cleanly."""
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'viral.db'}")

    vt = pytest.importorskip("src.tasks.video_tasks")
    from src.database import db

    app = vt.create_app_context()
    with app.app_context():
        db.create_all()
        from src.models.project import Project
        from src.models.task import Task
        from src.models.user import User

        owner = User(username="viral-owner", email="viral-owner@t.com",
                     password_hash="x")
        db.session.add(owner)
        db.session.flush()
        project = Project(title="viral", user_id=owner.id,
                          voice_type="female", status="draft")
        db.session.add(project)
        db.session.flush()
        record = Task(project_id=project.id,
                      task_type="viral_clip_detection",
                      status="pending",
                      celery_task_id="fake-viral-celery-id")
        db.session.add(record)
        db.session.commit()
        project_id = project.id

    class FakeStorage:
        def get_object(self, key):
            return b"\x00\x00\x00\x18ftypmp42"

    monkeypatch.setattr(vt, "get_storage", lambda: FakeStorage())

    # One moment so the ffmpeg loop runs; detection itself is not under test.
    monkeypatch.setattr(
        "src.services.video.viral_detector.detect_viral_moments",
        lambda src, count=5: [{"start": 0, "end": 2, "score": 1.0,
                               "hook": "h"}])

    def boom(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(
            1, cmd, output="", stderr="Encoder error: bad video stream")

    monkeypatch.setattr(vt.subprocess, "run", boom)

    with app.app_context():
        with pytest.raises(RuntimeError, match="bad video stream"):
            vt.detect_viral_clips_task.run.__func__(
                _FakeTaskSelf(), project_id, "storage/incoming.mp4", count=1)

        failed = vt.find_task_record(
            "fake-viral-celery-id", project_id, "viral_clip_detection")
        assert failed is not None
        assert failed.status == "failed"
        assert "bad video stream" in (failed.error_message or "")

        # materialized temp input copy was cleaned up — no leak
        leftovers = [
            f for f in os.listdir(tempfile.gettempdir())
            if f.startswith(f"viral_{project_id}_")
        ]
        assert leftovers == []


def test_viral_task_rejects_invalid_video_key(tmp_path, monkeypatch):
    """Traversal video_key -> ValueError, failed task record, storage and
    ffmpeg are never reached."""
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'viral-guard.db'}")

    vt = pytest.importorskip("src.tasks.video_tasks")
    from src.database import db

    app = vt.create_app_context()
    with app.app_context():
        db.create_all()
        from src.models.project import Project
        from src.models.task import Task
        from src.models.user import User

        owner = User(username="viral-guard", email="viral-guard@t.com",
                     password_hash="x")
        db.session.add(owner)
        db.session.flush()
        project = Project(title="viral-guard", user_id=owner.id,
                          voice_type="female", status="draft")
        db.session.add(project)
        db.session.flush()
        record = Task(project_id=project.id,
                      task_type="viral_clip_detection",
                      status="pending",
                      celery_task_id="fake-viral-guard-id")
        db.session.add(record)
        db.session.commit()
        project_id = project.id

    class _BoomStorage:
        def get_object(self, key):
            raise AssertionError("storage must not be reached for bad keys")

    monkeypatch.setattr(vt, "get_storage", lambda: _BoomStorage())

    def no_ffmpeg(cmd, *args, **kwargs):
        raise AssertionError("ffmpeg must not run for bad keys")

    monkeypatch.setattr(vt.subprocess, "run", no_ffmpeg)

    with app.app_context():
        with pytest.raises(ValueError, match="traversal segment"):
            vt.detect_viral_clips_task.run.__func__(
                _FakeTaskSelf("fake-viral-guard-id"), project_id,
                "videos/../../etc/passwd", count=1)

        failed = vt.find_task_record(
            "fake-viral-guard-id", project_id, "viral_clip_detection")
        assert failed.status == "failed"
        assert "traversal segment" in (failed.error_message or "")
