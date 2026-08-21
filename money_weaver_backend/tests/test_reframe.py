"""Tests for the smart 9:16 reframe service (Task 6).

All ffmpeg work is mocked via subprocess.run — no real encoding, no network,
no GPU. TRACK-mode ML deps (ultralytics/mediapipe) are simulated through
sys.modules poisoning/injection so tests stay deterministic whether or not the
heavy deps are installed in this venv.
"""
import sys
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
