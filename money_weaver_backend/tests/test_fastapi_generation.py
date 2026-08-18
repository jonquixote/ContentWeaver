"""Coverage for the FastAPI generation router: assembler/generative/batch-mix/
clone-voice queueing and the Celery task-status endpoint (all Celery mocked)."""
from types import SimpleNamespace
from unittest import mock

import pytest

from fastapi_app.routers import generation


def _user_id(client, headers):
    return client.get('/api/users/me', headers=headers).json()['id']


def _create_project(client, headers):
    r = client.post('/api/projects', json={'title': 'gen project'}, headers=headers)
    assert r.status_code == 201
    return r.json()['id']


def _create_voice(client, db_session, headers, tmp_path):
    uid = _user_id(client, headers)
    from src.models.voice import Voice
    ref = tmp_path / 'ref.wav'
    ref.write_bytes(b'RIFF')
    voice = Voice(user_id=uid, name='gen-voice', reference_audio_url=str(ref))
    db_session.add(voice)
    db_session.commit()
    return voice.id


def test_assembler_happy_path(client, auth_headers):
    pid = _create_project(client, auth_headers)
    with mock.patch.object(generation.generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='cel-1')):
        r = client.post('/api/generate/assembler',
                        json={'project_id': pid, 'prompt': 'a prompt'},
                        headers=auth_headers)
    assert r.status_code == 202
    body = r.json()
    assert body['message'] == 'Video generation started'
    assert body['celery_task_id'] == 'cel-1'
    assert body['project_id'] == pid
    assert body['settings']['voice_id'] is None


def test_assembler_foreign_project_is_403(client, auth_headers):
    client.post('/api/auth/register', json={
        'email': 'gen-other@test.com', 'username': 'genother', 'password': 'password123'})
    other = client.post('/api/auth/login', json={
        'email': 'gen-other@test.com', 'password': 'password123'}).json()['token']
    other_headers = {'Authorization': f'Bearer {other}'}
    pid = _create_project(client, auth_headers)
    assert client.post('/api/generate/assembler',
                       json={'project_id': pid, 'prompt': 'p'},
                       headers=other_headers).status_code == 403


def test_assembler_nonexistent_project_is_404(client, auth_headers):
    assert client.post('/api/generate/assembler',
                       json={'project_id': 9999, 'prompt': 'p'},
                       headers=auth_headers).status_code == 404


def test_assembler_missing_prompt_is_400(client, auth_headers):
    pid = _create_project(client, auth_headers)
    assert client.post('/api/generate/assembler',
                       json={'project_id': pid},
                       headers=auth_headers).status_code == 400


def test_assembler_queue_unavailable_is_503(client, auth_headers):
    pid = _create_project(client, auth_headers)
    with mock.patch.object(generation.generate_assembler_video_task, 'delay',
                           side_effect=RuntimeError('redis down')):
        r = client.post('/api/generate/assembler',
                        json={'project_id': pid, 'prompt': 'p'},
                        headers=auth_headers)
    assert r.status_code == 503
    assert 'Task queue unavailable' in r.json()['error']


def test_assembler_with_owned_voice(client, auth_headers, db_session, tmp_path):
    pid = _create_project(client, auth_headers)
    voice_id = _create_voice(client, db_session, auth_headers, tmp_path)
    with mock.patch.object(generation.generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='cel-2')):
        r = client.post('/api/generate/assembler',
                        json={'project_id': pid, 'prompt': 'p', 'voice_id': voice_id},
                        headers=auth_headers)
    assert r.status_code == 202
    assert r.json()['settings']['voice_id'] == voice_id


def test_generative_happy_path(client, auth_headers):
    pid = _create_project(client, auth_headers)
    with mock.patch.object(generation.generate_generative_video_task, 'delay',
                           return_value=mock.Mock(id='cel-3')):
        r = client.post('/api/generate/generative',
                        json={'project_id': pid, 'prompt': 'p'},
                        headers=auth_headers)
    assert r.status_code == 202
    assert r.json()['message'] == 'Generative video generation started'


def test_batch_mix_happy_path(client, auth_headers):
    pid = _create_project(client, auth_headers)
    with mock.patch.object(generation.batch_mix_videos_task, 'delay',
                           return_value=mock.Mock(id='cel-4')):
        r = client.post('/api/batch-mix',
                        json={'project_id': pid, 'variations': ['v1', 'v2']},
                        headers=auth_headers)
    assert r.status_code == 202
    assert r.json()['variations_count'] == 2


def test_batch_mix_requires_variations(client, auth_headers):
    pid = _create_project(client, auth_headers)
    assert client.post('/api/batch-mix',
                       json={'project_id': pid},
                       headers=auth_headers).status_code == 400


def test_clone_voice_happy_path(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr('fastapi_app.routers.generation.UPLOAD_FOLDER', str(tmp_path))
    with mock.patch.object(generation.clone_voice_task, 'delay',
                           return_value=mock.Mock(id='cel-5')):
        r = client.post('/api/clone-voice',
                        files={'audio': ('ref.wav', b'RIFF', 'audio/wav')},
                        data={'text': 'hello clone'},
                        headers=auth_headers)
    assert r.status_code == 202
    assert r.json()['message'] == 'Voice cloning started'


def test_clone_voice_requires_audio(client, auth_headers):
    assert client.post('/api/clone-voice', data={'text': 'hi'},
                       headers=auth_headers).status_code == 400


def test_clone_voice_requires_text(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr('fastapi_app.routers.generation.UPLOAD_FOLDER', str(tmp_path))
    r = client.post('/api/clone-voice',
                    files={'audio': ('ref.wav', b'RIFF', 'audio/wav')},
                    data={'text': ''},
                    headers=auth_headers)
    assert r.status_code == 400


def test_clone_voice_queue_unavailable_is_503(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr('fastapi_app.routers.generation.UPLOAD_FOLDER', str(tmp_path))
    with mock.patch.object(generation.clone_voice_task, 'delay',
                           side_effect=RuntimeError('redis down')):
        r = client.post('/api/clone-voice',
                        files={'audio': ('ref.wav', b'RIFF', 'audio/wav')},
                        data={'text': 'hi'},
                        headers=auth_headers)
    assert r.status_code == 503


def _queue_task(client, auth_headers, celery_id='cel-status-1'):
    pid = _create_project(client, auth_headers)
    with mock.patch.object(generation.generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id=celery_id)):
        client.post('/api/generate/assembler',
                    json={'project_id': pid, 'prompt': 'p'},
                    headers=auth_headers)


def _mock_result(client, auth_headers, monkeypatch, fake):
    from src.services.celery_app import celery_app
    _queue_task(client, auth_headers)
    monkeypatch.setattr(celery_app, 'AsyncResult', lambda tid: fake)
    return client.get('/api/task-status/cel-status-1', headers=auth_headers)


def test_task_status_pending(client, auth_headers, monkeypatch):
    r = _mock_result(client, auth_headers, monkeypatch,
                     SimpleNamespace(state='PENDING'))
    assert r.status_code == 200
    assert r.json()['status'] == 'Pending...'


def test_task_status_progress(client, auth_headers, monkeypatch):
    r = _mock_result(client, auth_headers, monkeypatch,
                     SimpleNamespace(state='PROGRESS',
                                     info={'current': 5, 'total': 10, 'status': 'half'}))
    assert r.status_code == 200
    assert r.json()['current'] == 5
    assert r.json()['total'] == 10


def test_task_status_success(client, auth_headers, monkeypatch):
    r = _mock_result(client, auth_headers, monkeypatch,
                     SimpleNamespace(state='SUCCESS', result={'video': 'v.mp4'}))
    assert r.status_code == 200
    assert r.json()['state'] == 'SUCCESS'
    assert r.json()['result'] == {'video': 'v.mp4'}


def test_task_status_failure_with_exception(client, auth_headers, monkeypatch):
    r = _mock_result(client, auth_headers, monkeypatch,
                     SimpleNamespace(state='FAILURE', info=RuntimeError('boom')))
    assert r.status_code == 200
    assert r.json()['state'] == 'FAILURE'


def test_task_status_unknown_task_is_404(client, auth_headers):
    assert client.get('/api/task-status/nope', headers=auth_headers).status_code == 404
