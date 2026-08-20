"""HTTP client for the MOSS-TTS voice-cloning microservice + Edge fallback chain.

Chain: MOSS-ONNX (8001) → Edge TTS (free, 300 voices, CPU) → Kokoro 82M → gTTS.
Edge path: `Voice.voice_engine=='edge'` or MOSS failure (connection/5xx).
"""
import asyncio
import os

import requests

TTS_URL = os.getenv('TTS_URL', 'http://localhost:8001')

VALID_ENGINES = {"moss", "edge", "kokoro", "gtts"}


def _edge_synthesize_sync(text: str, voice: str = "en-US-AriaNeural") -> bytes:
    """Sync wrapper around async edge_tts.synthesize."""
    from src.services.providers.edge_tts import synthesize as edge_synth

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # running loop (pytest-asyncio): create new loop in thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(asyncio.run, edge_synth(text, voice))
            return fut.result(timeout=30)
    return asyncio.run(edge_synth(text, voice))


def _base_url():
    return TTS_URL.rstrip('/')


def tts_health(timeout=5):
    """Return True iff the TTS service is up and its model is loaded.

    The model lazy-loads, so model_ready may be False while /tts still works.
    Health checks never raise (return False on any error).
    """
    try:
        r = requests.get(f'{_base_url()}/health', timeout=timeout)
        r.raise_for_status()
        return bool(r.json().get('model_ready', False))
    except Exception:
        return False


def synthesize(text, reference_audio_url=None, voice_id=None, timeout=300, voice_engine=None, voice="en-US-AriaNeural", **kwargs):
    """Synthesize speech and return raw audio bytes (WAV from MOSS, MP3 from Edge).

    Branching per request:
      * `voice_engine=='edge'` → Edge → Kokoro → gTTS (no MOSS/cloning).
      * no `reference_audio_url` (free path) → Edge → Kokoro → gTTS.
      * `reference_audio_url` (cloned voice) → MOSS(8001) → Edge → Kokoro →
        gTTS. MOSS transport errors and 5xx fall back to Edge; 4xx (bad
        input/ref contract) still raise HTTPError.
    Unknown `voice_engine` values raise ValueError.
    """
    # alias: ref_path / reference_audio_url / kwargs
    if reference_audio_url is None:
        reference_audio_url = kwargs.get("ref_path")
    if voice_engine is None:
        voice_engine = kwargs.get("voice_engine")
    if voice == "en-US-AriaNeural" and kwargs.get("voice"):
        voice = kwargs["voice"]
    language = kwargs.get("language", "en")

    if voice_engine is not None and voice_engine not in VALID_ENGINES:
        raise ValueError(
            f"Unknown voice_engine: {voice_engine!r}. Valid: {sorted(VALID_ENGINES)}"
        )

    def _edge():
        try:
            return _edge_synthesize_sync(text, voice)
        except Exception:
            return None

    # 1) Edge: explicit engine (even with a reference) or free path (no ref)
    if voice_engine == "edge":
        out = _edge()
        if out is not None:
            return out
    elif not reference_audio_url and voice_engine is None:
        out = _edge()
        if out is not None:
            return out

    # 2) MOSS attempt (requires reference); Edge fallback on transport/5xx
    if reference_audio_url is not None and voice_engine != "edge":
        try:
            r = requests.post(
                f'{_base_url()}/tts',
                json={
                    'text': text,
                    'reference_audio_url': reference_audio_url,
                    'voice_id': voice_id,
                },
                timeout=timeout,
            )
            r.raise_for_status()
            return r.content  # WAV bytes
        except requests.HTTPError as exc:
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                raise  # 4xx: bad input/ref contract — do not fall back
            out = _edge()
            if out is not None:
                return out
            raise  # Edge also failed → surface the MOSS 5xx
        except requests.RequestException:
            out = _edge()
            if out is not None:
                return out
            raise  # Edge also failed → surface the MOSS transport error

    # Final fallback: Kokoro → gTTS (file-based services)
    try:
        from src.services.video.advanced_tts_service import advanced_tts_service

        path = advanced_tts_service.generate_tts(text, model_type="kokoro", voice="af_heart")
        if path and os.path.exists(path):
            with open(path, "rb") as fh:
                return fh.read()
    except Exception:
        pass
    try:
        from src.services.video.tts_service import tts_service

        path = tts_service.generate_tts(text, language=language)
        if path and os.path.exists(path):
            with open(path, "rb") as fh:
                return fh.read()
    except Exception:
        pass
    # No provider succeeded
    raise RuntimeError("All TTS providers failed")
