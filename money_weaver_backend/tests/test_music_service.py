import os


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


def test_mix_voice_music_builds_duck_cmd(tmp_path):
    from src.services.video.music_service import mix_voice_music
    voice = tmp_path / "voice.wav"
    music = tmp_path / "music.mp3"
    out = tmp_path / "mixed.wav"
    cmd = mix_voice_music(str(voice), str(music), str(out))
    joined = " ".join(cmd)
    assert "sidechaincompress" in joined and "amix" in joined
    assert cmd[0] == "ffmpeg"
