def _register(client, email):
    username = email.split('@')[0]
    client.post('/api/auth/register', json={
        'email': email, 'username': username, 'password': 'password123'})
    r = client.post('/api/auth/login', json={'email': email, 'password': 'password123'})
    assert r.status_code == 200
    return {'Authorization': f"Bearer {r.json()['token']}"}


def test_studio_create_get_put_round_trip(client):
    auth = _register(client, 'studio-rt@test.com')
    r = client.post('/api/projects/studio', headers=auth)
    assert r.status_code == 201
    pid = r.json()['id']

    r = client.get(f'/api/projects/{pid}/studio', headers=auth)
    assert r.status_code == 404

    state = {'stage': 1, 'premise': {'text': 'cats'}, 'script': {},
             'storyboard': {'overrides': {}}, 'render': {},
             'updatedAt': '2026-08-27T00:00:00Z'}
    r = client.put(f'/api/projects/{pid}/studio', headers=auth, json=state)
    assert r.status_code == 200
    assert 'saved_at' in r.json()

    r = client.get(f'/api/projects/{pid}/studio', headers=auth)
    assert r.status_code == 200
    assert r.json()['studio_state'] == state


def test_studio_endpoints_enforce_ownership(client):
    auth_a = _register(client, 'studio-a@test.com')
    auth_b = _register(client, 'studio-b@test.com')

    pid = client.post('/api/projects/studio', headers=auth_a).json()['id']
    assert client.get(f'/api/projects/{pid}/studio', headers=auth_b).status_code in (403, 404)
    assert client.put(f'/api/projects/{pid}/studio', headers=auth_b,
                      json={'stage': 2}).status_code in (403, 404)
    assert client.get('/api/projects/999999/studio', headers=auth_a).status_code == 404
    assert client.post('/api/projects/studio').status_code in (401, 403)


def test_studio_put_persists_schema_version(client, auth_headers):
    pid = client.post('/api/projects/studio', headers=auth_headers).json()['id']
    state = {'stage': 2, 'schemaVersion': 2, 'premise': {'text': 'x'},
             'script': {}, 'storyboard': {'overrides': {}}, 'render': {},
             'updatedAt': '2026-08-27T00:00:00Z'}
    assert client.put(f'/api/projects/{pid}/studio', headers=auth_headers,
                      json=state).status_code == 200
    from src.models.project import Project
    from fastapi_app.db import db_session
    with db_session() as session:
        project = session.get(Project, pid)
        assert project.schema_version == 2