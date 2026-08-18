import json
import logging
import os
import subprocess
import tempfile
import uuid
from datetime import datetime
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from src.models.voice import Voice
from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.services.storage import (
    get_storage,
    is_valid_storage_key,
    resolve_reference_for_tts,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix='/api/voices', tags=['voices'])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FINAL_DIR = os.environ.get('FINAL_DIR', os.path.join(BASE_DIR, 'final'))
FFPROBE_PATH = os.environ.get('FFPROBE_PATH', '/usr/local/bin/ffprobe')
TTS_URL = os.environ.get('TTS_URL', 'http://localhost:8001')

# Reference-audio contract — aligned to the TTS microservice's real accepted
# contract (source of truth for end-to-end cloning): WAV/MP3, 3-20s, >=16kHz.
MAX_FILE_BYTES = 25 * 1024 * 1024  # matches the TTS service's download cap
MIN_DURATION = 3.0
MAX_DURATION = 20.0
MIN_SAMPLE_RATE = 16000

PREVIEW_TEXT = ("This is a preview using your cloned voice. "
                "Say hello to your new personal voice assistant.")


def validate_audio(path):
    """Validate a reference clip against the TTS service contract.

    Uses ffprobe. Enforces WAV/MP3 container, 3-20s duration and >=16kHz sample
    rate so a saved clip can never be rejected by the TTS boundary. Also caps
    file size. Raises ValueError on any violation.
    """
    if not os.path.isfile(path):
        raise ValueError('audio file not found')
    size = os.path.getsize(path)
    if size > MAX_FILE_BYTES:
        raise ValueError(f'audio file exceeds the {MAX_FILE_BYTES // (1024 * 1024)}MB size cap')
    r = subprocess.run(
        [FFPROBE_PATH, '-v', 'quiet', '-print_format', 'json',
         '-show_format', '-show_streams', path],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not r.stdout.strip():
        raise ValueError('could not read audio metadata')
    try:
        info = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise ValueError('could not read audio metadata')

    fmt = info.get('format') or {}
    format_name = (fmt.get('format_name') or '').lower()
    if not any(tag in format_name for tag in ('wav', 'wave', 'mp3', 'mpeg', 'mp2')):
        raise ValueError(f"unsupported audio format '{format_name}' (WAV/MP3 only)")

    try:
        duration = float(fmt.get('duration') or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if not (MIN_DURATION <= duration <= MAX_DURATION):
        raise ValueError(
            f'reference audio duration must be {MIN_DURATION:g}-{MAX_DURATION:g}s, got {duration:.1f}s'
        )

    sample_rates = []
    for stream in info.get('streams') or []:
        sr = stream.get('sample_rate')
        if sr:
            try:
                sample_rates.append(float(sr))
            except (TypeError, ValueError):
                pass
    if sample_rates and max(sample_rates) < MIN_SAMPLE_RATE:
        raise ValueError(
            f'reference audio sample rate {max(sample_rates):.0f}Hz < {MIN_SAMPLE_RATE}Hz required'
        )

    return duration


def _unlink_quiet(path):
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


class VoiceCreate(BaseModel):
    name: str
    consent: str
    reference_audio_url: str
    description: Optional[str] = None


@router.get('')
def list_voices(user=Depends(current_user), session=Depends(get_db)):
    voices = (session.query(Voice)
              .filter_by(user_id=user.id)
              .order_by(Voice.created_at.desc())
              .all())
    return [v.to_dict() for v in voices]


@router.post('', status_code=201)
def create_voice(body: VoiceCreate,
                 user=Depends(current_user),
                 session=Depends(get_db)):
    user_id = user.id
    payload = body.model_dump()

    name = (payload.get('name') or '').strip()
    if not name:
        raise HTTPException(400, 'Voice name is required')
    if len(name) > 100:
        raise HTTPException(400, 'name must be 100 characters or fewer')
    description = (payload.get('description') or '').strip()
    if len(description) > 300:
        raise HTTPException(400, 'description must be 300 characters or fewer')

    consent = (payload.get('consent') or '').strip().lower()
    if consent not in ('true', '1', 'yes', 'on'):
        raise HTTPException(400, 'Consent is required: you must confirm you own this voice')

    key = (payload.get('reference_audio_url') or '').strip()
    if not is_valid_storage_key(key, user_id):
        raise HTTPException(400, 'reference_audio_url must be a valid uploaded audio key')

    storage = get_storage()
    try:
        data = storage.get_object(key)
    except Exception as e:
        raise HTTPException(400, f'Failed to fetch uploaded audio: {e}')

    ext = key.rsplit('.', 1)[1].lower()
    fd, tmp_path = tempfile.mkstemp(prefix='voice-ref-', suffix=f'.{ext}')
    try:
        with os.fdopen(fd, 'wb') as fh:
            fh.write(data)
        validate_audio(tmp_path)
    except ValueError as e:
        try:
            storage.delete_object(key)
        except Exception:
            pass
        raise HTTPException(400, str(e))
    except Exception as e:
        try:
            storage.delete_object(key)
        except Exception:
            pass
        raise HTTPException(400, f'Failed to validate audio: {e}')
    finally:
        _unlink_quiet(tmp_path)

    voice = Voice(
        user_id=user_id,
        name=name,
        reference_audio_url=key,
        description=description,
        consent_confirmed_at=datetime.utcnow(),
    )
    session.add(voice)
    session.commit()
    return voice.to_dict()


@router.delete('/{voice_id}', status_code=204)
def delete_voice(voice_id: int,
                 user=Depends(current_user),
                 session=Depends(get_db)):
    voice = session.get(Voice, voice_id)
    if not voice:
        raise HTTPException(404, 'Voice not found')
    if voice.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    ref = voice.reference_audio_url
    session.delete(voice)
    session.commit()
    if is_valid_storage_key(ref, voice.user_id):
        try:
            get_storage().delete_object(ref)
        except Exception as e:
            logger.warning('failed to delete storage object %r: %s', ref, e)
    else:
        _unlink_quiet(ref)
    return Response(status_code=204)


@router.post('/{voice_id}/preview')
def preview_voice(voice_id: int,
                  user=Depends(current_user),
                  session=Depends(get_db)):
    user_id = user.id
    voice = session.get(Voice, voice_id)
    if not voice:
        raise HTTPException(404, 'Voice not found')
    if voice.user_id != user_id:
        raise HTTPException(403, 'Forbidden')

    ref = voice.reference_audio_url
    if is_valid_storage_key(ref, voice.user_id):
        storage = get_storage()
        try:
            if not storage.object_exists(ref):
                raise HTTPException(410, 'Reference audio file is missing from storage')
            ref = resolve_reference_for_tts(ref)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(503, f'Voice preview service is unavailable: {e}')
    elif not os.path.isfile(ref):
        raise HTTPException(410, 'Reference audio file is missing from storage')

    try:
        resp = requests.post(
            f'{TTS_URL.rstrip("/")}/tts',
            json={
                'text': PREVIEW_TEXT,
                'reference_audio_url': ref,
                'voice_id': str(voice.id),
            },
            timeout=120,
        )
    except requests.RequestException as e:
        raise HTTPException(503, f'Voice preview service is unavailable: {e}')

    if resp.status_code != 200:
        raise HTTPException(502, f'Voice synthesis failed: {resp.text[:500]}')

    os.makedirs(FINAL_DIR, exist_ok=True)
    preview_name = f'voice_preview_{voice.id}_{uuid.uuid4().hex}.wav'
    preview_path = os.path.join(FINAL_DIR, preview_name)
    with open(preview_path, 'wb') as fh:
        fh.write(resp.content)

    voice.last_used_at = datetime.utcnow()
    session.commit()
    return {'preview_url': f'/final/{preview_name}'}
