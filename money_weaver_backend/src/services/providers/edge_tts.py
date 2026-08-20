"""Edge TTS provider — free, CPU, 300 voices, MIT.

Wraps `edge-tts==7.x` Communicate API. Returns raw audio bytes (mp3 container
for MVP; caller `assembly_service` already handles mp3 refs). Provides static
voice list for offline/CI; full list via `edge_tts.list_voices()`.
"""
import asyncio
import inspect
import os
import tempfile

try:
    import edge_tts
except ImportError:  # allow collection/mocking when lib not installed
    import sys
    import types

    edge_tts = types.ModuleType("edge_tts")

    class _FakeCommunicate:
        def __init__(self, *a, **k):
            raise RuntimeError("edge-tts not installed")

    edge_tts.Communicate = _FakeCommunicate  # type: ignore[attr-defined]
    sys.modules["edge_tts"] = edge_tts


async def synthesize(text: str, voice: str = "en-US-AriaNeural") -> bytes:
    """Synthesize `text` with Edge TTS `voice`. Returns raw audio bytes (MP3).

    Real `edge_tts.Communicate` streams MP3 (24kHz, single stream). Handles
    both the real lib (sync ctor, async save) and the test mock
    `async def fake_comm` returning a coroutine.
    """
    if not text or not text.strip():
        raise ValueError("text required")
    # tempfile must survive await; use delete=False
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        path = tf.name
    try:
        comm = edge_tts.Communicate(text, voice)  # type: ignore[attr-defined,call-arg]
        if inspect.isawaitable(comm):
            comm = await comm
        # Support async context-manager mock (optional)
        # Normal path: comm.save(path) is async
        result = comm.save(path)
        if inspect.isawaitable(result):
            await result
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def list_voices():
    """Return MVP static voice list. Full list via `edge_tts.list_voices()` when online."""
    return ["en-US-AriaNeural", "en-US-GuyNeural", "en-GB-SoniaNeural"]
