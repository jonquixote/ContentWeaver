"""Smoke tests for the FastAPI app: JSON health + auth round-trip.

The Flask server never implemented /api/health (its static catch-all answered
text/html). The FastAPI migration flips that contract: /api/health returns
JSON. These tests exercise the FastAPI app directly via its TestClient.
"""

import pytest
from fastapi.testclient import TestClient

from fastapi_app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def test_health_returns_json(client):
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.headers['content-type'].startswith('application/json')
    assert r.json() == {'status': 'ok'}


def test_register_login_me_logout_blocklist(client):
    email = 'smoke@example.com'
    r = client.post('/api/auth/register', json={
        'email': email, 'username': 'smoketest', 'password': 'password123'})
    assert r.status_code == 201
    body = r.json()
    assert body['user']['email'] == email
    assert body['user']['username'] == 'smoketest'
    assert set(body['user']) == {'id', 'username', 'email', 'created_at', 'updated_at'}
    token = body['token']
    headers = {'Authorization': f'Bearer {token}'}

    r = client.get('/api/auth/me', headers=headers)
    assert r.status_code == 200
    assert r.json()['id'] == body['user']['id']

    r = client.get('/api/auth/me')
    assert r.status_code == 401
    assert r.json() == {'error': 'Missing token'}

    r = client.post('/api/auth/logout', headers=headers)
    assert r.status_code == 200
    assert r.json() == {'message': 'Logged out'}

    r = client.get('/api/auth/me', headers=headers)
    assert r.status_code == 401
    assert r.json() == {'error': 'Token revoked'}


def test_login_returns_user_and_token(client):
    client.post('/api/auth/register', json={
        'email': 'login@example.com', 'username': 'loginuser', 'password': 'password123'})
    r = client.post('/api/auth/login', json={
        'email': 'login@example.com', 'password': 'password123'})
    assert r.status_code == 200
    body = r.json()
    assert body['user']['email'] == 'login@example.com'
    assert body['token']


def test_register_duplicate_email_returns_400(client):
    client.post('/api/auth/register', json={
        'email': 'dup@example.com', 'username': 'dupuser', 'password': 'password123'})
    r = client.post('/api/auth/register', json={
        'email': 'dup@example.com', 'username': 'dupuser2', 'password': 'password123'})
    assert r.status_code == 400
    assert r.json() == {'error': 'User with this email already exists'}


def test_login_wrong_password_returns_401(client):
    client.post('/api/auth/register', json={
        'email': 'wrongpw@example.com', 'username': 'wrongpw', 'password': 'password123'})
    r = client.post('/api/auth/login', json={
        'email': 'wrongpw@example.com', 'password': 'nope'})
    assert r.status_code == 401
    assert r.json() == {'error': 'Invalid email or password'}