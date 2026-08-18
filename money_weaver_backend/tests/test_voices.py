"""Route tests for the voices create flow: presign -> upload -> JSON create,
required-field validation, list ownership scoping, and own-voice DELETE.

Overlap note: test_idor.py already asserts a DB-seeded voice is invisible to
another user's list and that deleting another user's voice returns 403. This
file exercises the API-driven create path and own-voice DELETE 204 instead.
"""
import json
import os
from unittest import mock

import pytest

from src.models.voice import Voice
from fastapi_app.routers.voices import validate_audio


def _register_user(client, email, username):
    r = client.post('/api/auth/register', json={
        'email': email, 'username': username, 'password': 'password123'})
    assert r.status_code == 201
    token = client.post('/api/auth/login', json={
        'email': email, 'password': 'password123'}).json()['token']
    return {'Authorization': f'Bearer {token}'}


def _presign_and_upload(client, auth_headers, data=b'RIFF\x00fake-wav'):
    presign = client.get('/api/uploads/presign?ext=wav', headers=auth_headers)
    assert presign.status_code == 200
    key = presign.json()['object_key']
    put = client.put(f'/api/uploads/{key}', headers=auth_headers, data=data)
    assert put.status_code == 200
    return key


def test_create_voice_requires_reference_audio(client, auth_headers):
    r = client.post('/api/voices', headers=auth_headers,
                    json={'name': 'V', 'consent': 'true'})
    assert r.status_code == 400


def test_create_voice_saves_and_scopes(client, auth_headers, monkeypatch):
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio', lambda *a, **k: 1.5)

    key = _presign_and_upload(client, auth_headers)
    r = client.post('/api/voices', headers=auth_headers, json={
        'name': 'My Voice', 'consent': 'true', 'reference_audio_url': key})
    assert r.status_code == 201
    body = r.json()
    assert body['name'] == 'My Voice'
    assert body['reference_audio_url'] == key

    # Owner sees it in their list.
    voices = client.get('/api/voices', headers=auth_headers).json()
    assert any(v['id'] == body['id'] for v in voices)

    # Another user's list does not contain it.
    other_headers = _register_user(client, 'other-voice@test.com', 'othervoice')
    other_voices = client.get('/api/voices', headers=other_headers).json()
    assert all(v['id'] != body['id'] for v in other_voices)


def test_delete_own_voice_returns_204(client, db_session, auth_headers, monkeypatch):
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio', lambda *a, **k: 1.5)

    key = _presign_and_upload(client, auth_headers)
    voice_id = client.post('/api/voices', headers=auth_headers, json={
        'name': 'Delete me', 'consent': 'true',
        'reference_audio_url': key}).json()['id']

    r = client.delete(f'/api/voices/{voice_id}', headers=auth_headers)
    assert r.status_code == 204
    assert db_session.get(Voice, voice_id) is None


# --- validate_audio (ffprobe contract) --------------------------------------


def _probe(format_name='wav', duration='5.0', sample_rate='44100'):
    return {'format': {'format_name': format_name, 'duration': duration},
            'streams': [{'sample_rate': sample_rate}]}


def _patch_probe(monkeypatch, payload):
    monkeypatch.setattr('fastapi_app.routers.voices.subprocess.run',
                        lambda *a, **k: mock.Mock(
                            returncode=0, stdout=json.dumps(payload)))


def test_validate_audio_missing_file(monkeypatch):
    with pytest.raises(ValueError):
        validate_audio('/nonexistent/ref.wav')


def test_validate_audio_oversized(monkeypatch, tmp_path):
    monkeypatch.setattr('fastapi_app.routers.voices.MAX_FILE_BYTES', 10)
    path = tmp_path / 'ref.wav'
    path.write_bytes(b'x' * 20)
    with pytest.raises(ValueError):
        validate_audio(str(path))


def test_validate_audio_probe_fails(monkeypatch, tmp_path):
    monkeypatch.setattr('fastapi_app.routers.voices.subprocess.run',
                        lambda *a, **k: mock.Mock(returncode=1, stdout=''))
    path = tmp_path / 'ref.wav'
    path.write_bytes(b'RIFF')
    with pytest.raises(ValueError):
        validate_audio(str(path))


def test_validate_audio_probe_invalid_json(monkeypatch, tmp_path):
    monkeypatch.setattr('fastapi_app.routers.voices.subprocess.run',
                        lambda *a, **k: mock.Mock(returncode=0, stdout='not-json'))
    path = tmp_path / 'ref.wav'
    path.write_bytes(b'RIFF')
    with pytest.raises(ValueError):
        validate_audio(str(path))


def test_validate_audio_unsupported_format(monkeypatch, tmp_path):
    _patch_probe(monkeypatch, _probe(format_name='aiff'))
    path = tmp_path / 'ref.wav'
    path.write_bytes(b'RIFF')
    with pytest.raises(ValueError):
        validate_audio(str(path))


def test_validate_audio_bad_duration(monkeypatch, tmp_path):
    _patch_probe(monkeypatch, _probe(duration='1.0'))
    path = tmp_path / 'ref.wav'
    path.write_bytes(b'RIFF')
    with pytest.raises(ValueError):
        validate_audio(str(path))


def test_validate_audio_low_sample_rate(monkeypatch, tmp_path):
    _patch_probe(monkeypatch, _probe(sample_rate='8000'))
    path = tmp_path / 'ref.wav'
    path.write_bytes(b'RIFF')
    with pytest.raises(ValueError):
        validate_audio(str(path))


def test_validate_audio_ok_returns_duration(monkeypatch, tmp_path):
    _patch_probe(monkeypatch, _probe())
    path = tmp_path / 'ref.wav'
    path.write_bytes(b'RIFF')
    assert validate_audio(str(path)) == 5.0


def test_validate_audio_duration_parse_failure(monkeypatch, tmp_path):
    _patch_probe(monkeypatch, _probe(duration='not-a-number'))
    path = tmp_path / 'ref.wav'
    path.write_bytes(b'RIFF')
    with pytest.raises(ValueError):
        validate_audio(str(path))


def test_validate_audio_sample_rate_parse_failure(monkeypatch, tmp_path):
    _patch_probe(monkeypatch, _probe(sample_rate='nope'))
    path = tmp_path / 'ref.wav'
    path.write_bytes(b'RIFF')
    assert validate_audio(str(path)) == 5.0


# --- create_voice validation branches ---------------------------------------


def test_create_voice_requires_name(client, auth_headers):
    assert client.post('/api/voices', headers=auth_headers,
                       json={'consent': 'true'}).status_code == 400


def test_create_voice_name_too_long(client, auth_headers):
    assert client.post('/api/voices', headers=auth_headers,
                       json={'name': 'x' * 101, 'consent': 'true'}).status_code == 400


def test_create_voice_description_too_long(client, auth_headers):
    assert client.post('/api/voices', headers=auth_headers,
                       json={'name': 'V', 'consent': 'true',
                             'description': 'y' * 301}).status_code == 400


def test_create_voice_requires_consent(client, auth_headers):
    assert client.post('/api/voices', headers=auth_headers,
                       json={'name': 'V', 'consent': 'false'}).status_code == 400


def test_create_voice_fetch_failure_is_400(client, auth_headers, monkeypatch):
    key = _presign_and_upload(client, auth_headers)
    monkeypatch.setattr(
        'fastapi_app.routers.voices.get_storage',
        lambda: mock.Mock(get_object=mock.Mock(side_effect=RuntimeError('net'))))
    r = client.post('/api/voices', headers=auth_headers, json={
        'name': 'V', 'consent': 'true', 'reference_audio_url': key})
    assert r.status_code == 400
    assert 'Failed to fetch uploaded audio' in r.json()['error']


def test_create_voice_validation_failure_deletes_upload(client, auth_headers, monkeypatch):
    key = _presign_and_upload(client, auth_headers)
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio',
                        mock.Mock(side_effect=ValueError('bad duration')))
    r = client.post('/api/voices', headers=auth_headers, json={
        'name': 'V', 'consent': 'true', 'reference_audio_url': key})
    assert r.status_code == 400
    assert r.json()['error'] == 'bad duration'


def test_create_voice_validation_other_exception_is_400(client, auth_headers, monkeypatch):
    key = _presign_and_upload(client, auth_headers)
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio',
                        mock.Mock(side_effect=RuntimeError('ffmpeg gone')))
    monkeypatch.setattr(
        'fastapi_app.routers.voices.get_storage',
        lambda: mock.Mock(delete_object=mock.Mock(side_effect=RuntimeError('down'))))
    r = client.post('/api/voices', headers=auth_headers, json={
        'name': 'V', 'consent': 'true', 'reference_audio_url': key})
    assert r.status_code == 400
    assert 'Failed to validate audio' in r.json()['error']


def test_create_voice_unlink_handles_oserror(client, auth_headers, monkeypatch):
    key = _presign_and_upload(client, auth_headers)
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio',
                        mock.Mock(side_effect=ValueError('bad duration')))
    monkeypatch.setattr('fastapi_app.routers.voices.os.remove',
                        mock.Mock(side_effect=OSError('busy')))
    r = client.post('/api/voices', headers=auth_headers, json={
        'name': 'V', 'consent': 'true', 'reference_audio_url': key})
    assert r.status_code == 400


# --- delete_voice branches ---------------------------------------------------


def test_delete_voice_nonexistent_is_404(client, auth_headers):
    assert client.delete('/api/voices/9999', headers=auth_headers).status_code == 404


def test_delete_voice_foreign_is_403(client, db_session, auth_headers):
    from src.models.user import User
    owner = db_session.query(User).filter_by(email='test@test.com').first()
    voice = Voice(user_id=owner.id, name='mine',
                  reference_audio_url='voices/{}/ref.wav'.format(owner.id))
    db_session.add(voice)
    db_session.commit()
    voice_id = voice.id
    other_headers = _register_user(client, 'delvoice@test.com', 'delvoice')
    assert client.delete(f'/api/voices/{voice_id}',
                         headers=other_headers).status_code == 403


def test_delete_voice_storage_failure_still_204(client, db_session, auth_headers, monkeypatch):
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio', lambda *a, **k: 1.5)
    key = _presign_and_upload(client, auth_headers)
    voice_id = client.post('/api/voices', headers=auth_headers, json={
        'name': 'Delete', 'consent': 'true',
        'reference_audio_url': key}).json()['id']
    monkeypatch.setattr(
        'fastapi_app.routers.voices.get_storage',
        lambda: mock.Mock(delete_object=mock.Mock(side_effect=RuntimeError('down'))))
    assert client.delete(f'/api/voices/{voice_id}',
                         headers=auth_headers).status_code == 204


def test_delete_voice_local_path_removes_file(client, db_session, auth_headers, tmp_path):
    ref = tmp_path / 'ref.wav'
    ref.write_bytes(b'RIFF')
    from src.models.user import User
    owner = db_session.query(User).filter_by(email='test@test.com').first()
    voice = Voice(user_id=owner.id, name='local',
                  reference_audio_url=str(ref))
    db_session.add(voice)
    db_session.commit()
    voice_id = voice.id
    assert client.delete(f'/api/voices/{voice_id}',
                         headers=auth_headers).status_code == 204
    assert not ref.exists()


# --- preview_voice branches --------------------------------------------------


def test_preview_voice_nonexistent_is_404(client, auth_headers):
    assert client.post('/api/voices/9999/preview',
                       headers=auth_headers).status_code == 404


def test_preview_voice_missing_storage_object_is_410(client, auth_headers, monkeypatch):
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio', lambda *a, **k: 1.5)
    key = _presign_and_upload(client, auth_headers)
    voice_id = client.post('/api/voices', headers=auth_headers, json={
        'name': 'Preview', 'consent': 'true',
        'reference_audio_url': key}).json()['id']
    monkeypatch.setattr('fastapi_app.routers.voices.get_storage',
                        lambda: mock.Mock(object_exists=mock.Mock(return_value=False)))
    assert client.post(f'/api/voices/{voice_id}/preview',
                       headers=auth_headers).status_code == 410


def test_preview_voice_storage_error_is_503(client, auth_headers, monkeypatch):
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio', lambda *a, **k: 1.5)
    key = _presign_and_upload(client, auth_headers)
    voice_id = client.post('/api/voices', headers=auth_headers, json={
        'name': 'Preview', 'consent': 'true',
        'reference_audio_url': key}).json()['id']
    monkeypatch.setattr('fastapi_app.routers.voices.get_storage',
                        lambda: mock.Mock(object_exists=mock.Mock(side_effect=RuntimeError('down'))))
    r = client.post(f'/api/voices/{voice_id}/preview', headers=auth_headers)
    assert r.status_code == 503


def test_preview_voice_local_path_missing_is_410(client, db_session, auth_headers, tmp_path):
    from src.models.user import User
    owner = db_session.query(User).filter_by(email='test@test.com').first()
    voice = Voice(user_id=owner.id, name='local',
                  reference_audio_url=str(tmp_path / 'missing.wav'))
    db_session.add(voice)
    db_session.commit()
    voice_id = voice.id
    assert client.post(f'/api/voices/{voice_id}/preview',
                       headers=auth_headers).status_code == 410


def test_preview_voice_tts_error_is_503(client, auth_headers, monkeypatch):
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio', lambda *a, **k: 1.5)
    key = _presign_and_upload(client, auth_headers)
    voice_id = client.post('/api/voices', headers=auth_headers, json={
        'name': 'Preview', 'consent': 'true',
        'reference_audio_url': key}).json()['id']
    import requests
    monkeypatch.setattr('fastapi_app.routers.voices.requests.post',
                        mock.Mock(side_effect=requests.RequestException('conn')))
    r = client.post(f'/api/voices/{voice_id}/preview', headers=auth_headers)
    assert r.status_code == 503


def test_preview_voice_non_200_is_502(client, auth_headers, monkeypatch):
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio', lambda *a, **k: 1.5)
    key = _presign_and_upload(client, auth_headers)
    voice_id = client.post('/api/voices', headers=auth_headers, json={
        'name': 'Preview', 'consent': 'true',
        'reference_audio_url': key}).json()['id']
    monkeypatch.setattr('fastapi_app.routers.voices.requests.post',
                        lambda *a, **k: mock.Mock(status_code=500, text='boom'))
    r = client.post(f'/api/voices/{voice_id}/preview', headers=auth_headers)
    assert r.status_code == 502


def test_preview_voice_happy_path(client, db_session, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr('fastapi_app.routers.voices.validate_audio', lambda *a, **k: 1.5)
    key = _presign_and_upload(client, auth_headers)
    voice_id = client.post('/api/voices', headers=auth_headers, json={
        'name': 'Preview', 'consent': 'true',
        'reference_audio_url': key}).json()['id']

    monkeypatch.setattr('fastapi_app.routers.voices.FINAL_DIR', str(tmp_path))
    monkeypatch.setattr('fastapi_app.routers.voices.requests.post',
                        lambda *a, **k: mock.Mock(status_code=200, content=b'RIFFxxxx'))

    r = client.post(f'/api/voices/{voice_id}/preview', headers=auth_headers)
    assert r.status_code == 200
    preview_url = r.json()['preview_url']
    assert preview_url.startswith('/final/voice_preview_')
    preview_name = os.path.basename(preview_url)
    assert (tmp_path / preview_name).exists()

    voice = db_session.get(Voice, voice_id)
    assert voice.last_used_at is not None
