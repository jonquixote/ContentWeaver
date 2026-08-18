"""IDOR / owner-scoping tests: a user must not read or mutate another user's
projects, voices, or account via direct object references."""
from src.models.user import User
from src.models.project import Project
from src.models.voice import Voice


def _register_user(client, email, username):
    r = client.post('/api/auth/register', json={
        'email': email, 'username': username, 'password': 'password123'})
    assert r.status_code == 201
    token = client.post('/api/auth/login', json={
        'email': email, 'password': 'password123'}).json()['token']
    return {'Authorization': f'Bearer {token}'}


def _user_id(client, headers):
    return client.get('/api/users/me', headers=headers).json()['id']


def _add_voice(db_session, user_id, name='A voice'):
    voice = Voice(user_id=user_id, name=name,
                  reference_audio_url=f'voices/{user_id}/ref.wav')
    db_session.add(voice)
    db_session.commit()
    return voice.id


def test_cannot_read_other_users_project(client, auth_headers):
    a_id = _user_id(client, auth_headers)
    created = client.post('/api/projects', json={'title': 'A project'},
                          headers=auth_headers)
    assert created.status_code == 201
    a_project_id = created.json()['id']
    b_headers = _register_user(client, 'idor@test.com', 'idoruser')
    assert client.get('/api/projects', headers=b_headers).json() == []
    assert client.get(f'/api/projects/{a_project_id}',
                      headers=b_headers).status_code == 403
    assert client.get(f'/api/projects/{a_project_id}',
                      headers=auth_headers).status_code == 200


def test_cannot_update_other_users_project(client, auth_headers):
    a_project_id = client.post('/api/projects', json={'title': 'A project'},
                               headers=auth_headers).json()['id']
    b_headers = _register_user(client, 'idor@test.com', 'idoruser')
    r = client.put(f'/api/projects/{a_project_id}', json={'title': 'Hijacked'},
                   headers=b_headers)
    assert r.status_code == 403
    assert client.get(f'/api/projects/{a_project_id}',
                      headers=auth_headers).json()['title'] == 'A project'


def test_cannot_delete_other_users_project(client, auth_headers):
    a_project_id = client.post('/api/projects', json={'title': 'A project'},
                               headers=auth_headers).json()['id']
    b_headers = _register_user(client, 'idor@test.com', 'idoruser')
    assert client.delete(f'/api/projects/{a_project_id}',
                         headers=b_headers).status_code == 403
    assert client.get(f'/api/projects/{a_project_id}',
                      headers=auth_headers).status_code == 200


def test_cannot_read_other_users_voice(client, db_session, auth_headers):
    a_id = _user_id(client, auth_headers)
    a_voice_id = _add_voice(db_session, a_id)
    b_headers = _register_user(client, 'idor@test.com', 'idoruser')
    voices = client.get('/api/voices', headers=b_headers).json()
    assert voices == []
    assert all(v['id'] != a_voice_id for v in voices)


def test_cannot_delete_other_users_voice(client, db_session, auth_headers):
    a_id = _user_id(client, auth_headers)
    a_voice_id = _add_voice(db_session, a_id)
    b_headers = _register_user(client, 'idor@test.com', 'idoruser')
    assert client.delete(f'/api/voices/{a_voice_id}',
                         headers=b_headers).status_code == 403
    assert db_session.get(Voice, a_voice_id) is not None


def test_cannot_preview_other_users_voice(client, db_session, auth_headers):
    a_id = _user_id(client, auth_headers)
    a_voice_id = _add_voice(db_session, a_id)
    b_headers = _register_user(client, 'idor@test.com', 'idoruser')
    assert client.post(f'/api/voices/{a_voice_id}/preview',
                       headers=b_headers).status_code == 403


def test_cannot_read_other_user_record(client, auth_headers):
    a_id = _user_id(client, auth_headers)
    b_headers = _register_user(client, 'idor@test.com', 'idoruser')
    assert client.get(f'/api/users/{a_id}', headers=b_headers).status_code == 403


def test_cannot_update_other_user_record(client, auth_headers):
    a_id = _user_id(client, auth_headers)
    b_headers = _register_user(client, 'idor@test.com', 'idoruser')
    r = client.put(f'/api/users/{a_id}', json={'username': 'hijacked'},
                   headers=b_headers)
    assert r.status_code == 403


def test_cannot_delete_other_user(client, auth_headers):
    a_id = _user_id(client, auth_headers)
    b_headers = _register_user(client, 'idor@test.com', 'idoruser')
    r = client.delete(f'/api/users/{a_id}', headers=b_headers)
    assert r.status_code == 403
    assert client.get('/api/users/me', headers=auth_headers).status_code == 200
