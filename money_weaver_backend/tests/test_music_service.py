import os

import pytest


def test_pick_music_returns_none_when_manifest_missing(monkeypatch, tmp_path):
    from src.services.video import music_service as ms
    monkeypatch.setattr(ms, "_MANIFEST_PATH", str(tmp_path / "missing.yaml"))
    assert ms.pick_music("tech", duration=30) is None


def test_pick_music_matches_niche_mood(monkeypatch, tmp_path):
    from src.services.video import music_service as ms
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "tracks:\n"
        "  - file: upbeat_01.mp3\n"
        "    mood: energetic\n"
        "  - file: calm_01.mp3\n"
        "    mood: neutral\n"
    )
    monkeypatch.setattr(ms, "_MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(ms, "_MUSIC_DIR", str(tmp_path))
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    pick = ms.pick_music("general", duration=30)
    assert pick == os.path.join(str(tmp_path), "calm_01.mp3")


def test_pick_music_skips_missing_files(monkeypatch, tmp_path):
    from src.services.video import music_service as ms
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("tracks:\n  - file: gone.mp3\n    mood: neutral\n")
    monkeypatch.setattr(ms, "_MANIFEST_PATH", str(manifest))
    monkeypatch.setattr(ms, "_MUSIC_DIR", str(tmp_path))
    assert ms.pick_music("general", duration=30) is None


def test_mix_voice_music_real_ffmpeg(tmp_path):
    """Execute the mix cmd against real ffmpeg with lavfi-generated inputs.

    Validates the filter graph end-to-end (parse + run), not just substrings.
    Skips when the ffmpeg binary is absent."""
    import shutil
    import subprocess

    from src.services.video.music_service import mix_voice_music

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg binary not available")

    voice = tmp_path / "voice.wav"
    music = tmp_path / "music.wav"
    out = tmp_path / "mixed.wav"
    for path, freq in ((voice, 440), (music, 220)):
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi",
             "-i", f"sine=frequency={freq}:duration=1", str(path)],
            check=True, capture_output=True,
        )

    cmd = mix_voice_music(str(voice), str(music), str(out))
    assert cmd[0] == "ffmpeg"
    subprocess.run(cmd, check=True, capture_output=True)
    assert out.exists() and out.stat().st_size > 0
