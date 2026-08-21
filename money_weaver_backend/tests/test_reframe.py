"""Tests for the smart 9:16 reframe service (Task 6).

All ffmpeg work is mocked via subprocess.run — no real encoding, no network,
no GPU. TRACK-mode ML deps (ultralytics/mediapipe) are simulated through
sys.modules poisoning/injection so tests stay deterministic whether or not the
heavy deps are installed in this venv.
"""
import os
import subprocess
import sys
import tempfile
import types

import pytest

from src.services.video import reframe_service


def _vf(cmd):
    """Extract the filtergraph string from a mocked ffmpeg command."""
    return cmd[cmd.index("-filter_complex") + 1]


@pytest.fixture()
def mock_run(monkeypatch):
    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)

    monkeypatch.setattr(reframe_service.subprocess, "run", fake_run)
    return calls


def test_reframe_general_returns_mp4_path(mock_run):
    out = reframe_service.reframe("/tmp/in.mp4", "general")
    assert out.endswith(".mp4")
    assert len(mock_run) == 1


def test_reframe_default_mode_is_general(mock_run):
    out = reframe_service.reframe("/tmp/in.mp4")
    assert out.endswith(".mp4")
    assert "boxblur" in _vf(mock_run[0])


def test_reframe_general_ffmpeg_cmd_construction(mock_run):
    out = reframe_service.reframe("/tmp/in.mp4", "general")
    cmd = mock_run[0]

    assert cmd[0] == "ffmpeg"
    assert "-y" in cmd
    assert "/tmp/in.mp4" in cmd          # input
    assert cmd[-1] == out                # output path is last arg

    vf = _vf(cmd)
    # blur-bg composite: blurred bg fills 1080x1920, fg fits and centers on top
    assert "scale=1080:1920" in vf
    assert "crop=1080:1920" in vf
    assert "boxblur" in vf
    assert "overlay=(W-w)/2:(H-h)/2" in vf

    # foreground mapped from the composite, audio copied through untouched
    assert "-map" in cmd
    assert "[out]" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "copy"


def test_reframe_track_import_error_falls_back_to_general(mock_run, monkeypatch):
    # A None entry in sys.modules makes `import ultralytics` raise ImportError,
    # simulating a worker without the heavy ML deps installed.
    monkeypatch.setitem(sys.modules, "ultralytics", None)
    monkeypatch.setitem(sys.modules, "mediapipe", None)

    general_out = reframe_service.reframe("/tmp/in.mp4", "general")
    track_out = reframe_service.reframe("/tmp/in.mp4", "track")

    assert track_out.endswith(".mp4")
    # fallback produced the exact same GENERAL filtergraph as an explicit
    # GENERAL call (paths differ; the filtergraph must not).
    assert _vf(mock_run[0]) == _vf(mock_run[1])
    assert general_out != track_out


def test_reframe_track_with_deps_present_still_degrades_to_general(
    mock_run, monkeypatch
):
    """TRACK is stubbed for now: even with YOLO/MediaPipe importable it uses
    the GENERAL blur-bg pipeline until the openshorts reframe_v2 port lands."""
    fake_ultralytics = types.ModuleType("ultralytics")
    fake_ultralytics.YOLO = lambda *a, **k: types.SimpleNamespace(
        predict=lambda img: []
    )
    fake_mediapipe = types.ModuleType("mediapipe")
    fake_mediapipe.FaceDetection = lambda *a, **k: types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)
    monkeypatch.setitem(sys.modules, "mediapipe", fake_mediapipe)

    out = reframe_service.reframe("/tmp/in.mp4", "track")

    assert out.endswith(".mp4")
    assert len(mock_run) == 1
    assert "boxblur" in _vf(mock_run[0])


def test_reframe_output_lands_in_managed_final_dir(mock_run):
    """Outputs go to the served backend/final dir, not a per-call mkdtemp."""
    out = reframe_service.reframe("/tmp/in.mp4", "general")
    assert out.startswith(reframe_service.OUTPUT_DIR)
    assert os.path.basename(out).endswith("_9x16.mp4")


def test_reframe_unknown_mode_raises_value_error(mock_run):
    with pytest.raises(ValueError, match="unknown reframe mode"):
        reframe_service.reframe("/tmp/in.mp4", "diagonal")
    assert len(mock_run) == 0


class _FakeTaskSelf:
    """Stand-in for the Celery task instance (no broker/backend required)."""

    def __init__(self, tid="fake-reframe-celery-id"):
        self.request = types.SimpleNamespace(id=tid)

    def update_state(self, *args, **kwargs):
        pass


def test_reframe_task_ffmpeg_failure_marks_failed_and_cleans_temp(
    tmp_path, monkeypatch
):
    """CalledProcessError from ffmpeg -> Celery FAILURE, failed task record,
    and the materialized temp input copy is unlinked (no leak)."""
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    # setenv (not raw assignment) so the temp DATABASE_URL is restored after
    # the test instead of leaking a dead sqlite path into later modules.
    monkeypatch.setenv(
        "DATABASE_URL", f"sqlite:///{tmp_path / 'reframe.db'}")

    vt = pytest.importorskip("src.tasks.video_tasks")
    from src.database import db

    app = vt.create_app_context()
    with app.app_context():
        db.create_all()
        from src.models.project import Project
        from src.models.task import Task
        from src.models.user import User

        owner = User(username="rf-owner", email="rf@t.com", password_hash="x")
        db.session.add(owner)
        db.session.flush()
        project = Project(title="rf", user_id=owner.id,
                          voice_type="female", status="draft")
        db.session.add(project)
        db.session.flush()
        record = Task(project_id=project.id, task_type="reframe_vertical",
                      status="pending", celery_task_id="fake-reframe-celery-id")
        db.session.add(record)
        db.session.commit()
        project_id = project.id

    class FakeStorage:
        def get_object(self, key):
            return b"\x00\x00\x00\x18ftypmp42"

    monkeypatch.setattr(vt, "get_storage", lambda: FakeStorage())

    def boom(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(reframe_service.subprocess, "run", boom)

    with app.app_context():
        with pytest.raises(subprocess.CalledProcessError):
            vt.reframe_for_vertical.run.__func__(
                _FakeTaskSelf(), project_id, "storage/incoming.mp4",
                mode="general",
            )

        # materialized temp input was cleaned up — no leak
        leftovers = [
            f for f in os.listdir(tempfile.gettempdir())
            if f.startswith(f"reframe_{project_id}_")
        ]
        assert leftovers == []

        # task record flipped to failed with the error captured
        failed = vt.find_task_record(
            "fake-reframe-celery-id", project_id, "reframe_vertical")
        assert failed is not None
        assert failed.status == "failed"
        assert "returned non-zero exit status" in (failed.error_message or "")


# ---------------------------------------------------------------------------
# video_key path guard (final review fix)
# ---------------------------------------------------------------------------

def test_validate_video_key_accepts_namespaced_keys():
    vt = pytest.importorskip("src.tasks.video_tasks")
    assert vt.validate_video_key("videos/1/2/9.mp4") == "videos/1/2/9.mp4"
    assert vt.validate_video_key("clips/1/2/clip_0.mp4")
    assert vt.validate_video_key("storage/incoming.mp4")


@pytest.mark.parametrize("bad", [
    "/etc/passwd",
    "../../etc/passwd",
    "videos/../../etc/passwd",
    "videos/../secret.mp4",
    "~/secret.mp4",
    "C:\\windows\\system32\\config.sys",
    "",
    None,
    123,
    "not-a-namespace/key.mp4",
])
def test_validate_video_key_rejects_unsafe(bad):
    vt = pytest.importorskip("src.tasks.video_tasks")
    with pytest.raises(ValueError):
        vt.validate_video_key(bad)


def test_reframe_task_rejects_invalid_video_key(tmp_path, monkeypatch):
    """Absolute path video_key -> ValueError, failed task record, and the
    storage provider is never consulted."""
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv(
        "DATABASE_URL", f"sqlite:///{tmp_path / 'reframe-guard.db'}")

    vt = pytest.importorskip("src.tasks.video_tasks")
    from src.database import db

    app = vt.create_app_context()
    with app.app_context():
        db.create_all()
        from src.models.project import Project
        from src.models.task import Task
        from src.models.user import User

        owner = User(username="rf-guard", email="rf-guard@t.com",
                     password_hash="x")
        db.session.add(owner)
        db.session.flush()
        project = Project(title="rf-guard", user_id=owner.id,
                          voice_type="female", status="draft")
        db.session.add(project)
        db.session.flush()
        record = Task(project_id=project.id, task_type="reframe_vertical",
                      status="pending",
                      celery_task_id="fake-reframe-guard-id")
        db.session.add(record)
        db.session.commit()
        project_id = project.id

    class _BoomStorage:
        def get_object(self, key):
            raise AssertionError("storage must not be reached for bad keys")

    monkeypatch.setattr(vt, "get_storage", lambda: _BoomStorage())

    with app.app_context():
        with pytest.raises(ValueError, match="filesystem path"):
            vt.reframe_for_vertical.run.__func__(
                _FakeTaskSelf("fake-reframe-guard-id"), project_id,
                "/etc/passwd", mode="general")

        failed = vt.find_task_record(
            "fake-reframe-guard-id", project_id, "reframe_vertical")
        assert failed.status == "failed"
        assert "filesystem path" in (failed.error_message or "")
