"""Chatterbox zero-shot voice cloning (MIT, resemble-ai/chatterbox).

Opt-in: requires `pip install chatterbox-tts` (pulls torch/torchaudio) and
CHATTERBOX_ENABLED=true. Clones a voice from a ~5-10s reference wav.
"""
import os

CHATTERBOX_ENABLED = os.getenv("CHATTERBOX_ENABLED", "false").lower() == "true"

_MODEL = None


def _get_model():
    global _MODEL
    if _MODEL is None:
        from chatterbox.tts import ChatterboxTTS
        _MODEL = ChatterboxTTS.from_pretrained(device="cpu")
    return _MODEL


def synthesize(text, reference_audio_path, exaggeration=0.5):
    """Clone-speak `text` in the reference voice. Returns wav bytes."""
    if not CHATTERBOX_ENABLED:
        raise RuntimeError("chatterbox disabled (set CHATTERBOX_ENABLED=true)")
    import tempfile
    import torchaudio  # runtime dep of chatterbox save path; lazy (torch absent in main venv)

    model = _get_model()
    wav = model.generate(text, audio_prompt_path=reference_audio_path,
                         exaggeration=exaggeration)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        torchaudio.save(tmp.name, wav, model.sr)
        with open(tmp.name, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass
