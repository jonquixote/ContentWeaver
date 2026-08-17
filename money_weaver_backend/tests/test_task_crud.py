"""CRUD coverage for the DB-backed /api/tasks routes: list (with/without
project_id), create, get, update, delete — plus the status route's message and
media-resolution branches (_progress_message, _resolve_media_url,
_resolve_result_media).

The Celery-backed queue endpoint (/api/generate/assembler) is exercised in
test_tasks.py and test_video_generation_routes.py; here the routes are driven
directly against the DB (SQLite via conftest).
"""
import json

import pytest

from src.database import db
from src.models.task import Task


def _register_user(client, email, username):
    r = client.post('/api/auth/register', json={
        'email': email, 'username': username, 'password': 'password123'})
    assert r.status_code == 201
    token = client.post('/api/auth/login', json={
        'email': email, 'password': 'password123'}).get_json()['token']
    return {'Authorization': f'Bearer {token}'}


def _create_project(client, headers, title='CRUD project'):
    r = client.post('/api/projects', json={'title': title}, headers=headers)
    assert r.status_code == 201
    return r.get_json()['id']


def _create_task(client, headers, project_id, task_type='video_assembly', **extra):
    r = client.post('/api/tasks', headers=headers,
                    json={'project_id': project_id, 'task_type': task_type, **extra})
    assert r.status_code == 201
    return r.get_json()


# --- GET /api/tasks ---------------------------------------------------------


def test_get_tasks_returns_empty_when_user_has_no_projects(client, auth_headers):
    r = client.get('/api/tasks', headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json() == []


def test_get_tasks_lists_all_user_tasks_without_project_id(client, auth_headers):
    p1 = _create_project(client, auth_headers, title='Project one')
    p2 = _create_project(client, auth_headers, title='Project two')
    t1 = _create_task(client, auth_headers, p1)
    t2 = _create_task(client, auth_headers, p2, task_type='script_generation')

    body = client.get('/api/tasks', headers=auth_headers).get_json()
    ids = {t['id'] for t in body}
    assert t1['id'] in ids and t2['id'] in ids


def test_get_tasks_filters_by_project_id(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    p2 = _create_project(client, auth_headers, title='Other')
    _create_task(client, auth_headers, p1)
    other = _create_task(client, auth_headers, p2)

    body = client.get(f'/api/tasks?project_id={p1}', headers=auth_headers).get_json()
    assert all(t['id'] != other['id'] for t in body)


def test_get_tasks_for_foreign_project_is_403(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    _create_task(client, auth_headers, p1)
    other_headers = _register_user(client, 'other-tasks@test.com', 'othertasks')
    assert client.get(f'/api/tasks?project_id={p1}',
                      headers=other_headers).status_code == 403


# --- POST /api/tasks --------------------------------------------------------


def test_create_task_requires_project_id_and_task_type(client, auth_headers):
    assert client.post('/api/tasks', headers=auth_headers,
                       json={}).status_code == 400
    assert client.post('/api/tasks', headers=auth_headers,
                       json={'project_id': 1}).status_code == 400


def test_create_task_project_not_found(client, auth_headers):
    assert client.post('/api/tasks', headers=auth_headers,
                       json={'project_id': 9999, 'task_type': 'x'}).status_code == 404


def test_create_task_foreign_project_is_403(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    other_headers = _register_user(client, 'create-other@test.com', 'createother')
    assert client.post('/api/tasks', headers=other_headers,
                       json={'project_id': p1, 'task_type': 'x'}).status_code == 403


def test_create_task_persists_row_with_ownership(client, app, auth_headers):
    p1 = _create_project(client, auth_headers)
    body = _create_task(client, auth_headers, p1, status='running',
                        celery_task_id='cel-42')
    assert body['task_type'] == 'video_assembly'
    assert body['status'] == 'running'
    assert body['celery_task_id'] == 'cel-42'
    with app.app_context():
        task = db.session.get(Task, body['id'])
        assert task is not None
        assert task.project_id == p1
        assert task.status == 'running'
        assert task.celery_task_id == 'cel-42'


# --- GET /api/tasks/<id> ----------------------------------------------------


def test_get_task_returns_single(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    r = client.get(f"/api/tasks/{created['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()['id'] == created['id']


def test_get_task_nonexistent_is_404(client, auth_headers):
    assert client.get('/api/tasks/9999', headers=auth_headers).status_code == 404


def test_get_task_foreign_is_403(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    other_headers = _register_user(client, 'get-other@test.com', 'getother')
    assert client.get(f"/api/tasks/{created['id']}",
                      headers=other_headers).status_code == 403


def test_get_task_with_deleted_project_is_404(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    assert client.delete(f'/api/projects/{p1}', headers=auth_headers).status_code == 204
    assert client.get(f"/api/tasks/{created['id']}",
                      headers=auth_headers).status_code == 404


# --- PUT /api/tasks/<id> ----------------------------------------------------


def test_update_task_happy_path(client, app, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    r = client.put(f"/api/tasks/{created['id']}", headers=auth_headers, json={
        'status': 'running', 'progress': 50,
        'result': json.dumps({'video_url': 'videos/x.mp4'}),
        'error_message': None, 'celery_task_id': 'cel-9',
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body['status'] == 'running'
    assert body['progress'] == 50
    with app.app_context():
        task = db.session.get(Task, created['id'])
        assert task.status == 'running'
        assert task.progress == 50
        assert json.loads(task.result)['video_url'] == 'videos/x.mp4'


def test_update_task_foreign_is_403(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    other_headers = _register_user(client, 'put-other@test.com', 'putother')
    assert client.put(f"/api/tasks/{created['id']}", headers=other_headers,
                      json={'status': 'failed'}).status_code == 403


def test_update_task_nonexistent_is_404(client, auth_headers):
    assert client.put('/api/tasks/9999', headers=auth_headers,
                      json={'status': 'running'}).status_code == 404


def test_update_task_with_deleted_project_is_404(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    assert client.delete(f'/api/projects/{p1}', headers=auth_headers).status_code == 204
    assert client.put(f"/api/tasks/{created['id']}", headers=auth_headers,
                      json={'status': 'running'}).status_code == 404


def test_update_task_non_object_body_is_400(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    r = client.put(f"/api/tasks/{created['id']}", headers=auth_headers, data='null',
                   content_type='application/json')
    assert r.status_code == 400


# --- DELETE /api/tasks/<id> -------------------------------------------------


def test_delete_task_happy_path(client, app, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    assert client.delete(f"/api/tasks/{created['id']}",
                         headers=auth_headers).status_code == 204
    with app.app_context():
        assert db.session.get(Task, created['id']) is None


def test_delete_task_foreign_is_403(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    other_headers = _register_user(client, 'del-other@test.com', 'delother')
    assert client.delete(f"/api/tasks/{created['id']}",
                         headers=other_headers).status_code == 403
    assert client.get(f"/api/tasks/{created['id']}",
                      headers=auth_headers).status_code == 200


def test_delete_task_nonexistent_is_404(client, auth_headers):
    assert client.delete('/api/tasks/9999', headers=auth_headers).status_code == 404


def test_delete_task_with_deleted_project_is_404(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    assert client.delete(f'/api/projects/{p1}', headers=auth_headers).status_code == 204
    assert client.delete(f"/api/tasks/{created['id']}",
                         headers=auth_headers).status_code == 404


# --- GET /api/tasks/<id>/status ---------------------------------------------


def _set_task(client, headers, task_id, **fields):
    r = client.put(f'/api/tasks/{task_id}', headers=headers, json=fields)
    assert r.status_code == 200
    return r.get_json()


def test_status_completed_resolves_media_keys(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    _set_task(client, auth_headers, created['id'], status='completed', progress=100,
              result=json.dumps({'video_url': 'videos/a.mp4',
                                 'thumbnail_url': '/final/t.jpg'}))
    body = client.get(f"/api/tasks/{created['id']}/status",
                      headers=auth_headers).get_json()
    assert body['status'] == 'completed'
    assert body['message'] == 'Completed'
    assert body['video_url'] == '/media/videos/a.mp4'
    assert body['thumbnail_url'] == '/final/t.jpg'


def test_status_completed_with_non_dict_result(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    _set_task(client, auth_headers, created['id'], status='completed',
              result=json.dumps([1, 2, 3]))
    body = client.get(f"/api/tasks/{created['id']}/status",
                      headers=auth_headers).get_json()
    assert body['video_url'] is None
    assert body['thumbnail_url'] is None


def test_status_failed_uses_error_message(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    _set_task(client, auth_headers, created['id'], status='failed',
              error_message='boom', progress=0)
    body = client.get(f"/api/tasks/{created['id']}/status",
                      headers=auth_headers).get_json()
    assert body['status'] == 'failed'
    assert body['error'] == 'boom'
    assert body['message'] == 'boom'


def test_status_failed_without_message_defaults(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    _set_task(client, auth_headers, created['id'], status='failed',
              error_message=None)
    body = client.get(f"/api/tasks/{created['id']}/status",
                      headers=auth_headers).get_json()
    assert body['message'] == 'Task failed'


def test_status_nonexistent_is_404(client, auth_headers):
    assert client.get('/api/tasks/9999/status',
                      headers=auth_headers).status_code == 404


def test_status_with_deleted_project_is_404(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    assert client.delete(f'/api/projects/{p1}', headers=auth_headers).status_code == 204
    assert client.get(f"/api/tasks/{created['id']}/status",
                      headers=auth_headers).status_code == 404


def test_status_unparsable_result_is_tolerated(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    _set_task(client, auth_headers, created['id'], status='running',
              progress=5, result='not-json')
    body = client.get(f"/api/tasks/{created['id']}/status",
                      headers=auth_headers).get_json()
    assert body['status'] == 'running'
    assert body['video_url'] is None


@pytest.mark.parametrize('progress,message', [
    (5, 'Queued...'),
    (15, 'Generating script...'),
    (30, 'Generating voiceover...'),
    (60, 'Searching for stock footage...'),
    (85, 'Assembling video...'),
    (95, 'Generating thumbnail...'),
    (100, 'Completed'),
])
def test_status_progress_messages(client, auth_headers, progress, message):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    _set_task(client, auth_headers, created['id'], status='running',
              progress=progress)
    body = client.get(f"/api/tasks/{created['id']}/status",
                      headers=auth_headers).get_json()
    assert body['message'] == message


# --- _resolve_result_media / _resolve_media_url -----------------------------


def test_get_task_resolves_result_media_keys(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    _set_task(client, auth_headers, created['id'],
              result=json.dumps({'video_url': 'videos/a.mp4'}))
    body = client.get(f"/api/tasks/{created['id']}", headers=auth_headers).get_json()
    assert json.loads(body['result'])['video_url'] == '/media/videos/a.mp4'


def test_get_task_leaves_non_dict_result_untouched(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    _set_task(client, auth_headers, created['id'], result=json.dumps([1, 2]))
    body = client.get(f"/api/tasks/{created['id']}", headers=auth_headers).get_json()
    assert body['result'] == json.dumps([1, 2])


def test_get_task_leaves_non_json_result_untouched(client, auth_headers):
    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    _set_task(client, auth_headers, created['id'], result='garbage')
    body = client.get(f"/api/tasks/{created['id']}", headers=auth_headers).get_json()
    assert body['result'] == 'garbage'


def test_media_resolution_falls_back_on_storage_outage(client, auth_headers, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('storage down')
    monkeypatch.setattr('src.services.storage.get_storage', boom)

    p1 = _create_project(client, auth_headers)
    created = _create_task(client, auth_headers, p1)
    _set_task(client, auth_headers, created['id'], status='completed',
              result=json.dumps({'video_url': 'videos/a.mp4'}))
    status = client.get(f"/api/tasks/{created['id']}/status",
                        headers=auth_headers).get_json()
    assert status['video_url'] == 'videos/a.mp4'

    task = client.get(f"/api/tasks/{created['id']}", headers=auth_headers).get_json()
    assert json.loads(task['result'])['video_url'] == 'videos/a.mp4'