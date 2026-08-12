"""HTTP client for the MOSS-TTS voice-cloning microservice.

Shared client used by the video-generation tasks and the legacy clone-voice
flow (money_weaver_backend/tts_service, port 8001). The service lazily loads
the ~728MB ONNX model on the first /tts request (10-60s warm), so callers that
can tolerate a long first call use timeout=300 (the default).
"""
import os

import requests

TTS_URL = os.getenv('TTS_URL', 'http://localhost:8001')


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


def synthesize(text, reference_audio_url, voice_id=None, timeout=300):
    """Synthesize speech with a cloned voice and return the raw WAV bytes.

    POST {TTS_URL}/tts -> 200 (audio/wav, pcm_s16le 24kHz mono). Raises
    HTTPError on 400 (bad input/ref contract), 502 (ref fetch fail), 503
    (model load fail) or 500 (inference fail), and RequestException on any
    transport-level failure.
    """
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
