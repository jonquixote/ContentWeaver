"""Coverage for the FastAPI /api/templates router."""
import pytest


def _register(client, email, username):
    r = client.post('/api/auth/register', json={
        'email': email, 'username': username, 'password': 'password123'})
    assert r.status_code == 201
    token = client.post('/api/auth/login', json={
        'email': email, 'password': 'password123'}).json()['token']
    return {'Authorization': f'Bearer {token}'}


def _valid_payload(name='My template', **extra):
    payload = {'name': name, 'config': {'preset': 'youtube', 'duration': 30}}
    payload.update(extra)
    return payload


@pytest.fixture()
def other_headers(client):
    return _register(client, 'other-tpl@test.com', 'othertpl')


def test_list_templates_empty(client, auth_headers):
    r = client.get('/api/templates', headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_create_template_happy_path(client, auth_headers):
    r = client.post('/api/templates', headers=auth_headers,
                    json=_valid_payload(description='desc'))
    assert r.status_code == 201
    body = r.json()
    assert body['name'] == 'My template'
    assert body['config'] == {'preset': 'youtube', 'duration': 30}
    assert body['is_public'] is False


def test_create_template_requires_name(client, auth_headers):
    assert client.post('/api/templates', headers=auth_headers,
                       json={'config': {}}).status_code == 400


def test_create_template_requires_config(client, auth_headers):
    assert client.post('/api/templates', headers=auth_headers,
                       json={'name': 'x'}).status_code == 400


def test_create_template_name_too_long(client, auth_headers):
    assert client.post('/api/templates', headers=auth_headers,
                       json=_valid_payload(name='x' * 101)).status_code == 400


def test_create_template_config_must_be_object(client, auth_headers):
    assert client.post('/api/templates', headers=auth_headers,
                       json={'name': 'x', 'config': 'nope'}).status_code == 400


def test_get_template_own(client, auth_headers):
    tid = client.post('/api/templates', headers=auth_headers,
                      json=_valid_payload()).json()['id']
    r = client.get(f'/api/templates/{tid}', headers=auth_headers)
    assert r.status_code == 200
    assert r.json()['id'] == tid


def test_get_template_foreign_private_is_403(client, auth_headers, other_headers):
    tid = client.post('/api/templates', headers=auth_headers,
                      json=_valid_payload()).json()['id']
    assert client.get(f'/api/templates/{tid}',
                      headers=other_headers).status_code == 403


def test_get_public_template_is_accessible(client, auth_headers, other_headers):
    tid = client.post('/api/templates', headers=auth_headers,
                      json=_valid_payload(is_public=True)).json()['id']
    r = client.get(f'/api/templates/{tid}', headers=other_headers)
    assert r.status_code == 200
    assert r.json()['is_public'] is True


def test_get_template_nonexistent_is_404(client, auth_headers):
    assert client.get('/api/templates/9999', headers=auth_headers).status_code == 404


def test_update_template_happy_path(client, auth_headers):
    tid = client.post('/api/templates', headers=auth_headers,
                      json=_valid_payload()).json()['id']
    r = client.put(f'/api/templates/{tid}', headers=auth_headers,
                   json={'name': 'Renamed', 'config': {'preset': 'tiktok'},
                         'is_public': True})
    assert r.status_code == 200
    body = r.json()
    assert body['name'] == 'Renamed'
    assert body['config'] == {'preset': 'tiktok'}
    assert body['is_public'] is True


def test_update_template_bad_config_is_400(client, auth_headers):
    tid = client.post('/api/templates', headers=auth_headers,
                      json=_valid_payload()).json()['id']
    r = client.put(f'/api/templates/{tid}', headers=auth_headers,
                   json={'config': 'nope'})
    assert r.status_code == 400


def test_update_template_foreign_is_403(client, auth_headers, other_headers):
    tid = client.post('/api/templates', headers=auth_headers,
                      json=_valid_payload()).json()['id']
    assert client.put(f'/api/templates/{tid}', headers=other_headers,
                      json={'name': 'x'}).status_code == 403


def test_delete_template_happy_path(client, auth_headers):
    tid = client.post('/api/templates', headers=auth_headers,
                      json=_valid_payload()).json()['id']
    assert client.delete(f'/api/templates/{tid}',
                         headers=auth_headers).status_code == 204
    assert client.get(f'/api/templates/{tid}',
                      headers=auth_headers).status_code == 404


def test_delete_template_foreign_is_403(client, auth_headers, other_headers):
    tid = client.post('/api/templates', headers=auth_headers,
                      json=_valid_payload()).json()['id']
    assert client.delete(f'/api/templates/{tid}',
                         headers=other_headers).status_code == 403


def test_delete_template_nonexistent_is_404(client, auth_headers):
    assert client.delete('/api/templates/9999',
                         headers=auth_headers).status_code == 404


def test_templates_require_auth(client):
    assert client.get('/api/templates').status_code == 401
