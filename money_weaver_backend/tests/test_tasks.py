"""Task-creation route + task-state tests for the assembler workflow.

Fills gaps left by test_video_generation_routes.py (which covers the queue
endpoint's 202 / voice_id passthrough / ownership for the *voice*): here we
assert the created Task DB row (ownership via the owning project), the DB-only
status route, cross-user 403 on status, and the pending -> completed state
transition driven by the Celery task body with the whole media pipeline mocked
(no FFmpeg / real celery / storage network).
"""
import json
import types
from unittest import mock

from src.database import db
from src.models.task import Task
from src.models.project import Project


def _register_user(client, email, username):
    r = client.post('/api/auth/register', json={
        'email': email, 'username': username, 'password': 'password123'})
    assert r.status_code == 201
    token = client.post('/api/auth/login', json={
        'email': email, 'password': 'password123'}).get_json()['token']
    return {'Authorization': f'Bearer {token}'}


def _user_id(client, headers):
    return client.get('/api/users/me', headers=headers).get_json()['id']


def _create_project(client, auth_headers):
    r = client.post('/api/projects', json={'title': 'Task test project'},
                    headers=auth_headers)
    assert r.status_code == 201
    return r.get_json()['id']


class FakeTaskSelf:
    """Stand-in for the Celery task instance (no broker/backend required)."""

    def __init__(self, tid='fake-celery-id'):
        self.request = types.SimpleNamespace(id=tid)

    def update_state(self, *args, **kwargs):
        pass


def _invoke(task, *args, **kwargs):
    """Call a bind=True celery task body with a fake self."""
    return task.run.__func__(FakeTaskSelf(), *args, **kwargs)


def test_create_project_returns_id(client, auth_headers):
    r = client.post('/api/projects', json={'title': 'Fresh project'},
                    headers=auth_headers)
    assert r.status_code == 201
    assert isinstance(r.get_json()['id'], int)


def test_assembler_returns_task_id_and_persists_ownership(client, app, auth_headers):
    from src.tasks.video_tasks import generate_assembler_video_task
    user_id = _user_id(client, auth_headers)
    project_id = _create_project(client, auth_headers)

    with mock.patch.object(generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='fake-celery-id')) as delay:
        r = client.post('/api/generate/assembler',
                        json={'project_id': project_id, 'prompt': 'a prompt'},
                        headers=auth_headers)
    assert r.status_code == 202
    body = r.get_json()
    assert body['message'] == 'Video generation started'
    assert isinstance(body['task_id'], int)
    assert body['celery_task_id'] == 'fake-celery-id'
    assert body['project_id'] == project_id
    delay.assert_called_once()

    # DB-only status route: 200 with a status field (no Redis needed).
    status = client.get(f"/api/tasks/{body['task_id']}/status", headers=auth_headers)
    assert status.status_code == 200
    assert 'status' in status.get_json()

    # Task row belongs to the caller: project_id points at the created project
    # and that project belongs to the current user. (Task has no user_id column;
    # ownership is inferred through the project.)
    with app.app_context():
        task = db.session.get(Task, body['task_id'])
        assert task is not None
        assert task.project_id == project_id
        assert task.celery_task_id == 'fake-celery-id'
        assert db.session.get(Project, project_id).user_id == user_id


def test_status_of_other_users_task_is_403(client, auth_headers):
    from src.tasks.video_tasks import generate_assembler_video_task
    project_id = _create_project(client, auth_headers)
    with mock.patch.object(generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='fake-celery-id')):
        task_id = client.post('/api/generate/assembler',
                              json={'project_id': project_id, 'prompt': 'p'},
                              headers=auth_headers).get_json()['task_id']

    other_headers = _register_user(client, 'other-task@test.com', 'othertask')
    assert client.get(f'/api/tasks/{task_id}/status',
                      headers=other_headers).status_code == 403


def test_assembler_task_state_transition_pending_to_completed(client, app, auth_headers, tmp_path):
    import src.tasks.video_tasks as vt
    from src.tasks.video_tasks import generate_assembler_video_task
    project_id = _create_project(client, auth_headers)

    with mock.patch.object(generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='fake-celery-id')):
        task_id = client.post('/api/generate/assembler',
                              json={'project_id': project_id, 'prompt': 'a prompt'},
                              headers=auth_headers).get_json()['task_id']

    # Fake media assets that must exist on disk for the task body to proceed.
    out = tmp_path / 'out.mp4'
    out.write_bytes(b'\x00\x00\x00\x18ftypmp42')
    thumb = tmp_path / 'thumb.jpg'
    thumb.write_bytes(b'\xff\xd8\xff\xe0')
    kokoro = tmp_path / 'kokoro.wav'
    kokoro.write_bytes(b'RIFF\x00')

    pipeline = [
        mock.patch.object(vt, 'llm_service'),
        mock.patch.object(vt, 'script_parsing_service'),
        mock.patch.object(vt, 'advanced_tts_service'),
        mock.patch.object(vt, 'stock_service'),
        mock.patch.object(vt, 'assembly_service'),
    ]
    for p in pipeline:
        p.start()
    vt.llm_service.generate_script.return_value = '# Title\n\nScript body.\n'
    vt.script_parsing_service.parse_script.return_value = {'scenes': []}
    vt.script_parsing_service.extract_voiceover_text.return_value = 'narration text'
    vt.advanced_tts_service.generate_tts.return_value = str(kokoro)
    vt.stock_service.get_stock_videos_for_script.return_value = ['a.mp4', 'b.mp4']
    vt.assembly_service.assemble_video.return_value = str(out)
    thumb_patch = mock.patch.object(vt, 'generate_thumbnail', return_value=str(thumb))
    thumb_patch.start()
    try:
        result = _invoke(generate_assembler_video_task, project_id=project_id,
                         prompt='a prompt')
    finally:
        thumb_patch.stop()
        for p in pipeline:
            p.stop()

    assert result['status'] == 'Video generation completed!'

    with app.app_context():
        task = db.session.get(Task, task_id)
        assert task is not None
        assert task.status == 'completed'
        assert task.progress == 100
        result_data = json.loads(task.result)
        assert result_data['status'] == 'completed'
        assert db.session.get(Project, project_id).status == 'completed'
