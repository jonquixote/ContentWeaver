"""Route tests: /api/users/me GET/PATCH/DELETE, auth-required, partial update rules."""
import pytest

from sqlalchemy.exc import IntegrityError

from src.models.project import Project
from src.models.user import User
from src.models.token_blocklist import TokenBlocklist


def _register(client, email, username, password):
    r = client.post('/api/auth/register', json={
        'email': email, 'username': username, 'password': password})
    assert r.status_code == 201
    token = client.post('/api/auth/login', json={
        'email': email, 'password': password}).json()['token']
    return {'Authorization': f'Bearer {token}'}


def _user_id(client, headers):
    return client.get('/api/users/me', headers=headers).json()['id']


@pytest.fixture()
def two_users(client):
    me = _register(client, 'me@t.com', 'me', 'pw-me')
    other = _register(client, 'other@t.com', 'other', 'pw-other')
    return me, other, _user_id(client, me), _user_id(client, other)


def test_get_me_requires_auth(client):
    assert client.get('/api/users/me').status_code == 401


def test_patch_me_requires_auth(client):
    assert client.patch('/api/users/me', json={'username': 'x'}).status_code == 401


def test_delete_me_requires_auth(client):
    assert client.delete('/api/users/me').status_code == 401


def test_get_me_returns_user(client, two_users):
    me, _other, me_id, _other_id = two_users
    resp = client.get('/api/users/me', headers=me)
    assert resp.status_code == 200
    data = resp.json()
    assert data['id'] == me_id
    assert data['username'] == 'me'
    assert data['email'] == 'me@t.com'


def test_patch_username(client, two_users):
    me, _other, _me_id, _other_id = two_users
    resp = client.patch('/api/users/me', json={'username': 'me2'}, headers=me)
    assert resp.status_code == 200
    assert resp.json()['username'] == 'me2'


def test_patch_password(client, db_session, two_users):
    me, _other, me_id, _other_id = two_users
    resp = client.patch('/api/users/me', json={'password': 'new-pass'}, headers=me)
    assert resp.status_code == 200
    user = db_session.get(User, me_id)
    assert user.verify_password('new-pass')
    assert not user.verify_password('pw-me')


def test_patch_password_non_string(client, two_users):
    me, _other, _me_id, _other_id = two_users
    resp = client.patch('/api/users/me', json={'password': 12345}, headers=me)
    assert resp.status_code == 400


def test_patch_blank_username_rejected(client, db_session, two_users):
    me, _other, me_id, _other_id = two_users
    resp = client.patch('/api/users/me', json={'username': '   '}, headers=me)
    assert resp.status_code == 400
    assert db_session.get(User, me_id).username == 'me'


def test_patch_blank_email_rejected(client, db_session, two_users):
    me, _other, me_id, _other_id = two_users
    resp = client.patch('/api/users/me', json={'email': ''}, headers=me)
    assert resp.status_code == 400
    assert db_session.get(User, me_id).email == 'me@t.com'


def test_patch_null_username_rejected(client, db_session, two_users):
    me, _other, me_id, _other_id = two_users
    resp = client.patch('/api/users/me', json={'username': None}, headers=me)
    assert resp.status_code == 400
    assert db_session.get(User, me_id).username == 'me'


def test_patch_null_email_rejected(client, db_session, two_users):
    me, _other, me_id, _other_id = two_users
    resp = client.patch('/api/users/me', json={'email': None}, headers=me)
    assert resp.status_code == 400
    assert db_session.get(User, me_id).email == 'me@t.com'


def test_create_user_requires_auth(client):
    resp = client.post('/api/users', json={
        'username': 'fresh', 'email': 'fresh@t.com', 'password': 'pw-fresh'})
    assert resp.status_code == 401


def test_create_user_creates(client, db_session, two_users):
    me, _other, _me_id, _other_id = two_users
    resp = client.post('/api/users', json={
        'username': 'fresh', 'email': 'fresh@t.com', 'password': 'pw-fresh'},
        headers=me)
    assert resp.status_code == 201
    data = resp.json()
    assert data['username'] == 'fresh'
    assert db_session.query(User).filter_by(username='fresh').first() is not None


def test_create_user_duplicate_username_conflict(client, db_session, two_users):
    me, _other, _me_id, _other_id = two_users
    resp = client.post('/api/users', json={
        'username': 'other', 'email': 'fresh@t.com', 'password': 'pw-fresh'},
        headers=me)
    assert resp.status_code == 409
    assert db_session.query(User).filter_by(email='fresh@t.com').first() is None


def test_create_user_duplicate_email_conflict(client, db_session, two_users):
    me, _other, _me_id, _other_id = two_users
    resp = client.post('/api/users', json={
        'username': 'fresh', 'email': 'other@t.com', 'password': 'pw-fresh'},
        headers=me)
    assert resp.status_code == 409
    assert db_session.query(User).filter_by(username='fresh').first() is None


def test_patch_duplicate_username_conflict(client, db_session, two_users):
    me, _other, me_id, _other_id = two_users
    resp = client.patch('/api/users/me', json={'username': 'other'}, headers=me)
    assert resp.status_code == 409
    assert db_session.get(User, me_id).username == 'me'


def test_patch_me_scoped_to_token_owner(client, db_session, two_users):
    me, other, me_id, _other_id = two_users
    resp = client.patch('/api/users/me', json={'username': 'other2'}, headers=other)
    assert resp.status_code == 200
    assert resp.json()['username'] == 'other2'
    assert db_session.get(User, me_id).username == 'me'


def test_delete_me_removes_user(client, db_session, two_users):
    me, _other, me_id, _other_id = two_users
    resp = client.delete('/api/users/me', headers=me)
    assert resp.status_code == 204
    assert db_session.get(User, me_id) is None


def test_delete_me_conflict_with_child_data(client, db_session, two_users):
    me, _other, me_id, _other_id = two_users
    client.post('/api/projects', json={'title': 'child project'}, headers=me)
    resp = client.delete('/api/users/me', headers=me)
    assert resp.status_code == 409
    assert 'projects' in resp.json()['error']
    assert db_session.get(User, me_id) is not None
    assert db_session.query(Project).count() == 1
    assert client.get('/api/users/me', headers=me).status_code == 200


def test_delete_me_409_on_fk_violation(client, db_session, two_users, monkeypatch):
    me, _other, me_id, _other_id = two_users
    db_session.add(Project(title='child project', user_id=me_id, voice_type='female'))
    db_session.commit()
    monkeypatch.setattr('fastapi_app.routers.users._user_has_child_data', lambda s, uid: False)

    def _boom(self, *a, **k):
        raise IntegrityError('DELETE FROM user', {}, Exception('fk'))
    monkeypatch.setattr('sqlalchemy.orm.Session.commit', _boom)

    resp = client.delete('/api/users/me', headers=me)
    assert resp.status_code == 409
    assert 'projects' in resp.json()['error']


def test_delete_me_revokes_token(client, db_session, two_users):
    import jwt
    me, _other, me_id, _other_id = two_users
    token = me['Authorization'].split(' ', 1)[1]
    jti = jwt.decode(token, 'test-secret', algorithms=['HS256'])['jti']
    resp = client.delete('/api/users/me', headers=me)
    assert resp.status_code == 204
    assert db_session.query(TokenBlocklist).filter_by(jti=jti).first() is not None
    assert client.get('/api/users/me', headers=me).status_code == 401


def test_deleted_user_token_rejected(client, two_users):
    _me, other, _me_id, other_id = two_users
    headers = other
    client.delete('/api/users/me', headers=headers)
    resp = client.get('/api/users/me', headers=headers)
    assert resp.status_code == 401