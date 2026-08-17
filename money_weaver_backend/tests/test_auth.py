"""Auth route tests: register/login flow, token enforcement, logout revocation,
and legacy werkzeug password-hash upgrade on login."""
import pytest

from werkzeug.security import generate_password_hash

from src.database import db
from src.models.user import User


def test_register_login_me_flow(client, auth_headers):
    r = client.get('/api/auth/me', headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()['email'] == 'test@test.com'


def test_register_returns_user_and_token(client):
    r = client.post('/api/auth/register', json={
        'email': 'fresh@test.com', 'username': 'fresh', 'password': 'password123'})
    assert r.status_code == 201
    data = r.get_json()
    assert data['user']['email'] == 'fresh@test.com'
    assert data['token']


def test_no_token_returns_401(client):
    assert client.get('/api/users/me').status_code == 401


def test_logout_revokes_token(client, auth_headers):
    assert client.post('/api/auth/logout', headers=auth_headers).status_code == 200
    assert client.get('/api/auth/me', headers=auth_headers).status_code == 401


def test_legacy_password_upgrade(client, app):
    r = client.post('/api/auth/register', json={
        'email': 'legacy@test.com', 'username': 'legacy', 'password': 'password123'})
    assert r.status_code == 201
    user_id = r.get_json()['user']['id']
    with app.app_context():
        user = db.session.get(User, user_id)
        user.password_hash = generate_password_hash('password123')
        db.session.commit()
    r = client.post('/api/auth/login', json={
        'email': 'legacy@test.com', 'password': 'password123'})
    assert r.status_code == 200
    assert r.get_json()['token']
    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.password_hash.startswith('$argon2')


def test_duplicate_register_returns_400(client):
    payload = {'email': 'dup@test.com', 'username': 'dup', 'password': 'password123'}
    assert client.post('/api/auth/register', json=payload).status_code == 201
    assert client.post('/api/auth/register', json=payload).status_code == 400