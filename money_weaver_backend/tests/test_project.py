"""Route coverage for the project update/delete happy paths, create validation,
and video_url media resolution (IDOR / cross-user 403 cases live in test_idor.py)."""
from src.database import db
from src.models.project import Project


def test_create_project_missing_title_is_400(client, auth_headers):
    assert client.post('/api/projects', headers=auth_headers,
                       json={}).status_code == 400


def test_update_project_happy_path(client, app, auth_headers):
    project_id = client.post('/api/projects', json={'title': 'Before'},
                             headers=auth_headers).get_json()['id']
    r = client.put(f'/api/projects/{project_id}', headers=auth_headers, json={
        'title': 'After', 'description': 'desc', 'status': 'completed',
        'workflow_type': 'assembler', 'script': '{"scenes": []}',
        'video_url': '/final/v.mp4',
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body['title'] == 'After'
    assert body['status'] == 'completed'
    assert body['video_url'] == '/final/v.mp4'
    with app.app_context():
        project = db.session.get(Project, project_id)
        assert project.title == 'After'
        assert project.description == 'desc'
        assert project.script == '{"scenes": []}'

    fetched = client.get(f'/api/projects/{project_id}',
                         headers=auth_headers).get_json()
    assert fetched['video_url'] == '/final/v.mp4'


def test_update_project_non_object_body_is_400(client, auth_headers):
    project_id = client.post('/api/projects', json={'title': 'Before'},
                             headers=auth_headers).get_json()['id']
    r = client.put(f'/api/projects/{project_id}', headers=auth_headers,
                   data='null', content_type='application/json')
    assert r.status_code == 400


def test_delete_project_happy_path(client, app, auth_headers):
    project_id = client.post('/api/projects', json={'title': 'Delete me'},
                             headers=auth_headers).get_json()['id']
    assert client.delete(f'/api/projects/{project_id}',
                         headers=auth_headers).status_code == 204
    assert client.get(f'/api/projects/{project_id}',
                      headers=auth_headers).status_code == 404
    with app.app_context():
        assert db.session.get(Project, project_id) is None


def test_project_video_url_resolved_via_presigned(client, auth_headers):
    project_id = client.post('/api/projects', json={'title': 'With video'},
                             headers=auth_headers).get_json()['id']
    client.put(f'/api/projects/{project_id}', headers=auth_headers,
               json={'video_url': 'videos/final.mp4'})
    body = client.get(f'/api/projects/{project_id}',
                      headers=auth_headers).get_json()
    assert body['video_url'] == '/media/videos/final.mp4'


def test_project_video_url_falls_back_on_storage_outage(client, auth_headers, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('storage down')
    monkeypatch.setattr('src.services.storage.get_storage', boom)

    project_id = client.post('/api/projects', json={'title': 'With video'},
                             headers=auth_headers).get_json()['id']
    client.put(f'/api/projects/{project_id}', headers=auth_headers,
               json={'video_url': 'videos/final.mp4'})
    body = client.get(f'/api/projects/{project_id}',
                      headers=auth_headers).get_json()
    assert body['video_url'] == 'videos/final.mp4'