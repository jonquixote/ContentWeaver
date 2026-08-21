import pytest


def _fake_chatterbox_module(monkeypatch):
    """Inject fake chatterbox.tts + torchaudio modules into sys.modules."""
    import sys
    import types

    fake_cb = types.ModuleType("chatterbox")
    fake_tts = types.ModuleType("chatterbox.tts")

    class FakeModel:
        sr = 24000
        def generate(self, text, audio_prompt_path=None, exaggeration=0.5):
            # plain object; only torchaudio.save touches it
            return object()

    fake_tts.ChatterboxTTS = type(
        "ChatterboxTTS", (),
        {"from_pretrained": classmethod(lambda cls, device=None: FakeModel())}
    )
    fake_cb.tts = fake_tts

    saved = {}
    fake_ta = types.ModuleType("torchaudio")
    def fake_save(path, wav, sr):
        with open(path, "wb") as fh:
            fh.write(b"RIFFfake-wavdata")
        saved["path"] = path
    fake_ta.save = fake_save
    monkeypatch.setitem(sys.modules, "chatterbox", fake_cb)
    monkeypatch.setitem(sys.modules, "chatterbox.tts", fake_tts)
    monkeypatch.setitem(sys.modules, "torchaudio", fake_ta)
    return saved


def test_disabled_flag_raises(monkeypatch):
    from src.services.providers import chatterbox_tts as cb
    monkeypatch.setattr(cb, "CHATTERBOX_ENABLED", False)
    with pytest.raises(RuntimeError, match="disabled"):
        cb.synthesize("hello", "/tmp/ref.wav")


def test_synthesize_returns_wav_bytes(monkeypatch, tmp_path):
    from src.services.providers import chatterbox_tts as cb
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"RIFFref")
    _fake_chatterbox_module(monkeypatch)
    monkeypatch.setattr(cb, "CHATTERBOX_ENABLED", True)
    out = cb.synthesize("hello world", str(ref))
    assert isinstance(out, bytes) and len(out) > 0
