"""Route tests for /api/voices (Phase 3, Task 2).

Covers the Voice model + owner-scoped CRUD routes + reference-audio validation
aligned to the TTS microservice contract (WAV/MP3, 3-20s, >=16kHz, 25MB cap) and
the preview endpoint's TTS-service call.

Run from repo root:
  ./money_weaver_backend/venv/bin/python -m unittest tests.test_voices_routes -v
"""
import io
import os
import re
import struct
import sys
import tempfile
import unittest
import wave

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'money_weaver_backend'))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

os.environ['SECRET_KEY'] = 'test-secret-key'
_TMP = tempfile.mkdtemp(prefix='voices_test_')
os.environ['UPLOAD_DIR'] = os.path.join(_TMP, 'uploads')
os.environ['FINAL_DIR'] = os.path.join(_TMP, 'final')
# Point at a port where nothing listens -> preview returns a clean 503.
os.environ['TTS_URL'] = 'http://127.0.0.1:1'

from unittest.mock import patch

from flask import Flask

from src.database import db
from src.models.user import User
from src.models.voice import Voice
from src.routes.voices import (
    FINAL_DIR,
    UPLOAD_DIR,
    MAX_DURATION,
    MAX_FILE_BYTES,
    MIN_DURATION,
    MIN_SAMPLE_RATE,
    validate_audio,
    voices_bp,
)

MAX_MB = MAX_FILE_BYTES // (1024 * 1024)


def make_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True
    db.init_app(app)
    with app.app_context():
        db.create_all()
    app.register_blueprint(voices_bp, url_prefix='/api')
    return app


def make_wav_bytes(seconds, rate=16000):
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b'\x00\x00' * int(seconds * rate))
    return buf.getvalue()


class VoicesTestCase(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.client = self.app.test_client()
        with self.app.app_context():
            self.user1 = User(username='voice_user1', email='u1@example.com')
            self.user1.hash_password('pw')
            self.user2 = User(username='voice_user2', email='u2@example.com')
            self.user2.hash_password('pw')
            db.session.add_all([self.user1, self.user2])
            db.session.commit()
            self.uid1 = self.user1.id
            self.uid2 = self.user2.id
            self.token1 = self.user1.generate_token()
            self.token2 = self.user2.generate_token()
        self.auth1 = {'Authorization': f'Bearer {self.token1}'}
        self.auth2 = {'Authorization': f'Bearer {self.token2}'}

    def post_voice(self, auth, name='My Voice', seconds=5, rate=16000,
                   consent='true', filename='clip.wav', description='', raw=None):
        data = {
            'name': name,
            'description': description,
            'consent': consent,
            'reference_audio': (io.BytesIO(raw if raw is not None else make_wav_bytes(seconds, rate)), filename),
        }
        return self.client.post('/api/voices', data=data,
                                content_type='multipart/form-data', headers=auth)

    def create_valid_voice(self, auth):
        return self.post_voice(auth)

    # ---- auth ----

    def test_list_voices_requires_auth(self):
        resp = self.client.get('/api/voices')
        self.assertEqual(resp.status_code, 401)

    def test_create_voice_requires_auth(self):
        resp = self.post_voice({})
        self.assertEqual(resp.status_code, 401)

    def test_delete_voice_requires_auth(self):
        resp = self.client.delete('/api/voices/1')
        self.assertEqual(resp.status_code, 401)

    def test_preview_voice_requires_auth(self):
        resp = self.client.post('/api/voices/1/preview')
        self.assertEqual(resp.status_code, 401)

    # ---- create: consent + validation ----

    def test_create_voice_missing_consent(self):
        resp = self.post_voice(self.auth1, consent='')
        self.assertEqual(resp.status_code, 400)

    def test_create_voice_missing_name(self):
        resp = self.post_voice(self.auth1, name='')
        self.assertEqual(resp.status_code, 400)

    def test_create_voice_disallowed_extension(self):
        resp = self.post_voice(self.auth1, filename='clip.txt')
        self.assertEqual(resp.status_code, 400)

    def test_create_voice_short_audio_rejected(self):
        resp = self.post_voice(self.auth1, seconds=1)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('duration', resp.get_json()['error'].lower())

    def test_create_voice_long_audio_rejected(self):
        resp = self.post_voice(self.auth1, seconds=21)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('duration', resp.get_json()['error'].lower())

    def test_create_voice_low_sample_rate_rejected(self):
        resp = self.post_voice(self.auth1, rate=8000)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('sample rate', resp.get_json()['error'].lower())

    def test_create_voice_oversize_rejected(self):
        big = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        try:
            big.truncate((MAX_MB + 1) * 1024 * 1024)
            with open(big.name, 'rb') as fh:
                data = {'name': 'big', 'consent': 'true',
                        'reference_audio': (fh, 'big.wav')}
                resp = self.client.post('/api/voices', data=data,
                                        content_type='multipart/form-data', headers=self.auth1)
            self.assertEqual(resp.status_code, 400)
            self.assertIn('cap', resp.get_json()['error'].lower())
        finally:
            os.unlink(big.name)

    def test_create_voice_valid(self):
        resp = self.create_valid_voice(self.auth1)
        self.assertEqual(resp.status_code, 201)
        body = resp.get_json()
        for key in ('id', 'user_id', 'name', 'reference_audio_url', 'description',
                    'created_at', 'consent_confirmed_at', 'last_used_at'):
            self.assertIn(key, body)
        self.assertEqual(body['user_id'], self.uid1)
        self.assertEqual(body['name'], 'My Voice')
        self.assertIsNotNone(body['consent_confirmed_at'])
        self.assertTrue(os.path.isfile(body['reference_audio_url']))
        self.assertIn(os.path.join('voices', ''), body['reference_audio_url'])
        self.assertIn(os.path.join(str(self.uid1), 'voices'), body['reference_audio_url'])
        self.assertRegex(os.path.basename(body['reference_audio_url']),
                         re.compile(r'^[0-9a-f]{32}\.wav$'))

    # ---- list ----

    def test_list_voices_owner_scoped(self):
        self.create_valid_voice(self.auth1)
        self.create_valid_voice(self.auth1)
        self.create_valid_voice(self.auth2)
        resp = self.client.get('/api/voices', headers=self.auth1)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.get_json()), 2)
        for v in resp.get_json():
            self.assertEqual(v['user_id'], self.uid1)

    # ---- delete ----

    def test_delete_voice_owner(self):
        created = self.create_valid_voice(self.auth1).get_json()
        ref = created['reference_audio_url']
        self.assertTrue(os.path.isfile(ref))
        resp = self.client.delete(f"/api/voices/{created['id']}", headers=self.auth1)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(os.path.isfile(ref))
        with self.app.app_context():
            self.assertIsNone(db.session.get(Voice, created['id']))

    def test_delete_voice_not_found(self):
        resp = self.client.delete('/api/voices/99999', headers=self.auth1)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()['error'], 'Voice not found')

    def test_delete_voice_cross_user_forbidden(self):
        created = self.create_valid_voice(self.auth1).get_json()
        resp = self.client.delete(f"/api/voices/{created['id']}", headers=self.auth2)
        self.assertEqual(resp.status_code, 403)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Voice, created['id']))
        self.assertTrue(os.path.isfile(created['reference_audio_url']))

    # ---- preview ----

    def test_preview_voice_not_found(self):
        resp = self.client.post('/api/voices/99999/preview', headers=self.auth1)
        self.assertEqual(resp.status_code, 404)

    def test_preview_voice_cross_user_forbidden(self):
        created = self.create_valid_voice(self.auth1).get_json()
        resp = self.client.post(f"/api/voices/{created['id']}/preview", headers=self.auth2)
        self.assertEqual(resp.status_code, 403)

    def test_preview_voice_service_down_clean_error(self):
        created = self.create_valid_voice(self.auth1).get_json()
        resp = self.client.post(f"/api/voices/{created['id']}/preview", headers=self.auth1)
        self.assertEqual(resp.status_code, 503)
        body = resp.get_json()
        self.assertIn('error', body)
        self.assertIn('unavailable', body['error'].lower())

    def test_preview_voice_success(self):
        created = self.create_valid_voice(self.auth1).get_json()
        fake_audio = make_wav_bytes(3)

        class FakeResp:
            status_code = 200
            content = fake_audio

            def json(self):
                return {}

        class FakeRequests:
            @staticmethod
            def post(url, json=None, timeout=None):
                self.assertIn('/tts', url)
                return FakeResp()

        with patch('src.routes.voices.requests', FakeRequests):
            resp = self.client.post(f"/api/voices/{created['id']}/preview", headers=self.auth1)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body['preview_url'].startswith('/final/'))
        fname = os.path.basename(body['preview_url'])
        self.assertTrue(os.path.isfile(os.path.join(FINAL_DIR, fname)))
        with self.app.app_context():
            voice = db.session.get(Voice, created['id'])
            self.assertIsNotNone(voice.last_used_at)

    def test_preview_voice_tts_error_502(self):
        created = self.create_valid_voice(self.auth1).get_json()

        class FakeResp:
            status_code = 400
            text = '{"detail": "bad reference audio"}'

            def json(self):
                return {'detail': 'bad reference audio'}

        class FakeRequests:
            @staticmethod
            def post(url, json=None, timeout=None):
                return FakeResp()

        with patch('src.routes.voices.requests', FakeRequests):
            resp = self.client.post(f"/api/voices/{created['id']}/preview", headers=self.auth1)
        self.assertEqual(resp.status_code, 502)
        self.assertIn('error', resp.get_json())

    # ---- validate_audio unit ----

    def test_validate_audio_ok(self):
        p = os.path.join(UPLOAD_DIR, 'unit_ok.wav')
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as fh:
            fh.write(make_wav_bytes(5))
        try:
            dur = validate_audio(p)
            self.assertAlmostEqual(dur, 5.0, places=1)
        finally:
            os.remove(p)

    def test_validate_audio_rejects_non_audio_content(self):
        p = os.path.join(UPLOAD_DIR, 'unit_junk.wav')
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'wb') as fh:
            fh.write(b'this is not a wav or mp3 file at all' * 1000)
        try:
            with self.assertRaises(ValueError):
                validate_audio(p)
        finally:
            os.remove(p)

    def test_validate_audio_constants(self):
        self.assertEqual(MIN_DURATION, 3.0)
        self.assertEqual(MAX_DURATION, 20.0)
        self.assertEqual(MIN_SAMPLE_RATE, 16000)
        self.assertEqual(MAX_FILE_BYTES, 25 * 1024 * 1024)


if __name__ == '__main__':
    unittest.main()
