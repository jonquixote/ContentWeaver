import json
import os
import subprocess
import uuid
from datetime import datetime

import requests
from flask import Blueprint, jsonify, request, g

from src.models.voice import Voice
from src.database import db
from src.auth import auth_required

voices_bp = Blueprint('voices', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', os.path.join(BASE_DIR, 'uploads'))
FINAL_DIR = os.environ.get('FINAL_DIR', os.path.join(BASE_DIR, 'final'))
FFPROBE_PATH = os.environ.get('FFPROBE_PATH', '/usr/local/bin/ffprobe')
TTS_URL = os.environ.get('TTS_URL', 'http://localhost:8001')

# Reference-audio contract — aligned to the TTS microservice's real accepted
# contract (source of truth for end-to-end cloning): WAV/MP3, 3-20s, >=16kHz.
ALLOWED_EXTENSIONS = {'wav', 'mp3'}
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


def _extension_allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _unlink_quiet(path):
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


@voices_bp.route('/voices', methods=['GET'])
@auth_required
def list_voices():
    voices = (Voice.query
              .filter_by(user_id=g.current_user['id'])
              .order_by(Voice.created_at.desc())
              .all())
    return jsonify([v.to_dict() for v in voices])


@voices_bp.route('/voices', methods=['POST'])
@auth_required
def create_voice():
    user_id = g.current_user['id']

    name = (request.form.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Voice name is required'}), 400
    if len(name) > 100:
        return jsonify({'error': 'name must be 100 characters or fewer'}), 400
    description = (request.form.get('description') or '').strip()
    if len(description) > 300:
        return jsonify({'error': 'description must be 300 characters or fewer'}), 400

    consent = (request.form.get('consent') or '').strip().lower()
    if consent not in ('true', '1', 'yes', 'on'):
        return jsonify({'error': 'Consent is required: you must confirm you own this voice'}), 400

    if 'reference_audio' not in request.files:
        return jsonify({'error': 'reference_audio file is required'}), 400
    audio = request.files['reference_audio']
    filename = audio.filename or ''
    if not filename or not _extension_allowed(filename):
        return jsonify({'error': 'reference_audio must be a WAV or MP3 file'}), 400
    ext = filename.rsplit('.', 1)[1].lower()

    voice_dir = os.path.join(UPLOAD_DIR, str(user_id), 'voices')
    os.makedirs(voice_dir, exist_ok=True)
    tmp_path = os.path.join(voice_dir, f'.tmp-{uuid.uuid4().hex}.{ext}')
    try:
        audio.save(tmp_path)
        validate_audio(tmp_path)
    except ValueError as e:
        _unlink_quiet(tmp_path)
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        _unlink_quiet(tmp_path)
        return jsonify({'error': f'Failed to save audio: {e}'}), 400

    final_path = os.path.join(voice_dir, f'{uuid.uuid4().hex}.{ext}')
    os.replace(tmp_path, final_path)

    voice = Voice(
        user_id=user_id,
        name=name,
        reference_audio_url=final_path,
        description=description,
        consent_confirmed_at=datetime.utcnow(),
    )
    db.session.add(voice)
    db.session.commit()
    return jsonify(voice.to_dict()), 201


@voices_bp.route('/voices/<int:voice_id>', methods=['DELETE'])
@auth_required
def delete_voice(voice_id):
    voice = Voice.query.get(voice_id)
    if not voice:
        return jsonify({'error': 'Voice not found'}), 404
    if voice.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    ref = voice.reference_audio_url
    db.session.delete(voice)
    db.session.commit()
    _unlink_quiet(ref)
    return '', 204


@voices_bp.route('/voices/<int:voice_id>/preview', methods=['POST'])
@auth_required
def preview_voice(voice_id):
    user_id = g.current_user['id']
    voice = Voice.query.get(voice_id)
    if not voice:
        return jsonify({'error': 'Voice not found'}), 404
    if voice.user_id != user_id:
        return jsonify({'error': 'Forbidden'}), 403
    if not os.path.isfile(voice.reference_audio_url):
        return jsonify({'error': 'Reference audio file is missing from storage'}), 410

    try:
        resp = requests.post(
            f'{TTS_URL.rstrip("/")}/tts',
            json={
                'text': PREVIEW_TEXT,
                'reference_audio_url': voice.reference_audio_url,
                'voice_id': str(voice.id),
            },
            timeout=120,
        )
    except requests.RequestException as e:
        return jsonify({
            'error': 'Voice preview service is unavailable',
            'details': str(e),
        }), 503

    if resp.status_code != 200:
        return jsonify({
            'error': 'Voice synthesis failed',
            'details': resp.text[:500],
        }), 502

    os.makedirs(FINAL_DIR, exist_ok=True)
    preview_name = f'voice_preview_{voice.id}_{uuid.uuid4().hex}.wav'
    preview_path = os.path.join(FINAL_DIR, preview_name)
    with open(preview_path, 'wb') as fh:
        fh.write(resp.content)

    voice.last_used_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'preview_url': f'/final/{preview_name}'})