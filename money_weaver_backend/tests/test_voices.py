"""Route tests for the voices create flow: presign -> upload -> JSON create,
required-field validation, list ownership scoping, and own-voice DELETE.

Overlap note: test_idor.py already asserts a DB-seeded voice is invisible to
another user's list and that deleting another user's voice returns 403. This
file exercises the API-driven create path and own-voice DELETE 204 instead.
"""
from src.database import db
from src.models.voice import Voice


def _register_user(client, email, username):
    r = client.post('/api/auth/register', json={
        'email': email, 'username': username, 'password': 'password123'})
    assert r.status_code == 201
    token = client.post('/api/auth/login', json={
        'email': email, 'password': 'password123'}).get_json()['token']
    return {'Authorization': f'Bearer {token}'}


def _presign_and_upload(client, auth_headers, data=b'RIFF\x00fake-wav'):
    presign = client.get('/api/uploads/presign?ext=wav', headers=auth_headers)
    assert presign.status_code == 200
    key = presign.get_json()['object_key']
    put = client.put(f'/api/uploads/{key}', headers=auth_headers, data=data)
    assert put.status_code == 200
    return key


def test_create_voice_requires_reference_audio(client, auth_headers):
    r = client.post('/api/voices', headers=auth_headers,
                    json={'name': 'V', 'consent': 'true'})
    assert r.status_code == 400


def test_create_voice_saves_and_scopes(client, auth_headers, monkeypatch):
    monkeypatch.setattr('src.routes.voices.validate_audio', lambda *a, **k: 1.5)

    key = _presign_and_upload(client, auth_headers)
    r = client.post('/api/voices', headers=auth_headers, json={
        'name': 'My Voice', 'consent': 'true', 'reference_audio_url': key})
    assert r.status_code == 201
    body = r.get_json()
    assert body['name'] == 'My Voice'
    assert body['reference_audio_url'] == key

    # Owner sees it in their list.
    voices = client.get('/api/voices', headers=auth_headers).get_json()
    assert any(v['id'] == body['id'] for v in voices)

    # Another user's list does not contain it.
    other_headers = _register_user(client, 'other-voice@test.com', 'othervoice')
    other_voices = client.get('/api/voices', headers=other_headers).get_json()
    assert all(v['id'] != body['id'] for v in other_voices)


def test_delete_own_voice_returns_204(client, app, auth_headers, monkeypatch):
    monkeypatch.setattr('src.routes.voices.validate_audio', lambda *a, **k: 1.5)

    key = _presign_and_upload(client, auth_headers)
    voice_id = client.post('/api/voices', headers=auth_headers, json={
        'name': 'Delete me', 'consent': 'true',
        'reference_audio_url': key}).get_json()['id']

    r = client.delete(f'/api/voices/{voice_id}', headers=auth_headers)
    assert r.status_code == 204
    with app.app_context():
        assert db.session.get(Voice, voice_id) is None
