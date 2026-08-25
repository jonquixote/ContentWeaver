"""Coverage for the FastAPI api-keys and models routers."""
from types import SimpleNamespace
from unittest import mock

import pytest

from fastapi_app.routers import api_keys


def _uid(client, auth_headers):
    return client.get('/api/users/me', headers=auth_headers).json()['id']


def test_add_api_key_happy_path(client, auth_headers):
    r = client.post('/api/api-keys', headers=auth_headers, json={
        'name': 'OpenAI', 'provider': 'openai', 'key': 'sk-test'})
    assert r.status_code == 201
    body = r.json()
    assert body['message'] == 'API key added successfully'
    assert body['api_key']['name'] == 'OpenAI'
    assert body['api_key']['provider'] == 'openai'


def test_add_api_key_requires_fields(client, auth_headers):
    assert client.post('/api/api-keys', headers=auth_headers,
                       json={}).status_code == 400
    assert client.post('/api/api-keys', headers=auth_headers,
                       json={'name': 'x'}).status_code == 400


def test_list_user_api_keys(client, auth_headers):
    _uid(client, auth_headers)
    client.post('/api/api-keys', headers=auth_headers, json={
        'name': 'OpenAI', 'provider': 'openai', 'key': 'sk-1'})
    r = client.get('/api/api-keys/user/1', headers=auth_headers)
    assert r.status_code == 200
    keys = r.json()['api_keys']
    assert len(keys) == 1
    assert keys[0]['name'] == 'OpenAI'


def test_list_other_user_api_keys_is_403(client, auth_headers):
    client.post('/api/auth/register', json={
        'email': 'other-api@test.com', 'username': 'other-api',
        'password': 'password123'})
    other = client.post('/api/auth/login', json={
        'email': 'other-api@test.com', 'password': 'password123'}).json()['token']
    other_headers = {'Authorization': f'Bearer {other}'}
    assert client.get('/api/api-keys/user/1',
                      headers=other_headers).status_code == 403


def test_delete_api_key_happy_path(client, auth_headers):
    key_id = client.post('/api/api-keys', headers=auth_headers, json={
        'name': 'K', 'provider': 'openai', 'key': 'sk-x'}).json()['api_key']['id']
    r = client.delete(f'/api/api-keys/{key_id}', headers=auth_headers)
    assert r.status_code == 200
    assert r.json()['message'] == 'API key deleted successfully'


def test_delete_api_key_foreign_or_missing_is_404(client, auth_headers):
    client.post('/api/api-keys', headers=auth_headers, json={
        'name': 'K', 'provider': 'openai', 'key': 'sk-x'})
    client.post('/api/auth/register', json={
        'email': 'del-api@test.com', 'username': 'del-api', 'password': 'password123'})
    other = client.post('/api/auth/login', json={
        'email': 'del-api@test.com', 'password': 'password123'}).json()['token']
    other_headers = {'Authorization': f'Bearer {other}'}
    assert client.delete('/api/api-keys/1', headers=other_headers).status_code == 404
    assert client.delete('/api/api-keys/9999', headers=auth_headers).status_code == 404


def test_test_api_key_openai_happy(client, auth_headers):
    with mock.patch.object(api_keys.litellm, 'completion', return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='ok'))])):
        r = client.post('/api/api-keys/test', headers=auth_headers,
                        json={'provider': 'openai', 'key': 'sk-abc'})
    assert r.status_code == 200
    assert r.json()['success'] is True
    assert r.json()['response'] == 'ok'


def test_test_api_key_failure_is_400(client, auth_headers):
    with mock.patch.object(api_keys.litellm, 'completion',
                           side_effect=Exception('boom')):
        r = client.post('/api/api-keys/test', headers=auth_headers,
                        json={'provider': 'openai', 'key': 'sk-abc'})
    assert r.status_code == 400
    assert r.json()['success'] is False
    assert r.json()['error'] == 'boom'


def test_test_api_key_unsupported_provider(client, auth_headers):
    r = client.post('/api/api-keys/test', headers=auth_headers,
                    json={'provider': 'nope', 'key': 'k'})
    assert r.status_code == 400


def test_test_api_key_missing_fields(client, auth_headers):
    assert client.post('/api/api-keys/test', headers=auth_headers,
                       json={}).status_code == 400


def test_models_happy_path(client, auth_headers):
    models = [{"id": "a-model", "provider": "openrouter"}]
    with mock.patch.object(api_keys.registry, 'list_models', return_value=models):
        r = client.get('/api/models', headers=auth_headers)
    assert r.status_code == 200
    assert r.json()['models'] == models


def test_models_requires_auth(client):
    assert client.get('/api/models').status_code == 401


def test_default_model(client, auth_headers, monkeypatch):
    """Default resolves to a real free model — pseudo-ids like openrouter/free
    (present in the live catalog but 404 on completions) must never win."""
    fake_catalog = [
        {"id": "openrouter/free", "provider": "openrouter", "display_name": "Free",
         "capabilities": {"chat": True}, "free": True},
        {"id": "nvidia/nemotron-3.5-lightning:free", "provider": "openrouter",
         "display_name": "Nemotron", "capabilities": {"chat": True}, "free": True},
        {"id": "paid/model", "provider": "openrouter", "display_name": "Paid",
         "capabilities": {"chat": True}, "free": False},
    ]
    monkeypatch.setattr(api_keys.registry, 'list_models', lambda force=False: fake_catalog)
    r = client.get('/api/models/default', headers=auth_headers)
    assert r.status_code == 200
    assert r.json()['default_model'] == 'nvidia/nemotron-3.5-lightning:free'
