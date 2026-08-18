"""Route tests: /api/generate/assembler and /api/generate/generative voice_id pass-through."""
from unittest import mock

import pytest

from src.models.voice import Voice

from fastapi_app.routers.generation import (
    _resolve_owned_voice,
    generate_assembler_video_task,
    generate_generative_video_task,
)


@pytest.fixture()
def owner(client):
    r = client.post('/api/auth/register', json={
        'email': 'owner@t.com', 'username': 'owner', 'password': 'pw-owner'})
    assert r.status_code == 201
    token = client.post('/api/auth/login', json={
        'email': 'owner@t.com', 'password': 'pw-owner'}).json()['token']
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture()
def other(client):
    r = client.post('/api/auth/register', json={
        'email': 'other@t.com', 'username': 'other', 'password': 'pw-other'})
    assert r.status_code == 201
    token = client.post('/api/auth/login', json={
        'email': 'other@t.com', 'password': 'pw-other'}).json()['token']
    return {'Authorization': f'Bearer {token}'}


def _user_id(client, headers):
    return client.get('/api/users/me', headers=headers).json()['id']


@pytest.fixture()
def owner_voice(client, db_session, owner, tmp_path):
    uid = _user_id(client, owner)
    ref = tmp_path / 'ref.wav'
    ref.write_bytes(b'RIFF\x00ref')
    voice = Voice(user_id=uid, name='v', reference_audio_url=str(ref))
    db_session.add(voice)
    db_session.commit()
    return voice.id


def _seed_project(client, headers):
    r = client.post('/api/projects', json={'title': 'p'}, headers=headers)
    assert r.status_code == 201
    return r.json()['id']


def test_assembler_passes_voice_id_to_task(client, owner, owner_voice):
    pid = _seed_project(client, owner)
    with mock.patch.object(generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='c-1')) as delay:
        resp = client.post(
            '/api/generate/assembler',
            json={'project_id': pid, 'prompt': 'p', 'voice_id': owner_voice},
            headers=owner)
    assert resp.status_code == 202
    delay.assert_called_once()
    _, kwargs = delay.call_args
    assert kwargs['voice_id'] == owner_voice


def test_assembler_rejects_unowned_voice(client, owner, other, owner_voice):
    pid = _seed_project(client, owner)
    resp = client.post(
        '/api/generate/assembler',
        json={'project_id': pid, 'prompt': 'p', 'voice_id': owner_voice},
        headers=other)
    assert resp.status_code == 403


def test_assembler_rejects_nonexistent_voice(client, owner):
    pid = _seed_project(client, owner)
    resp = client.post(
        '/api/generate/assembler',
        json={'project_id': pid, 'prompt': 'p', 'voice_id': 999999},
        headers=owner)
    assert resp.status_code == 404


def test_assembler_rejects_non_integer_voice_id(client, owner):
    pid = _seed_project(client, owner)
    resp = client.post(
        '/api/generate/assembler',
        json={'project_id': pid, 'prompt': 'p', 'voice_id': 'abc'},
        headers=owner)
    assert resp.status_code == 400


def test_generative_passes_voice_id_to_task(client, owner, owner_voice):
    pid = _seed_project(client, owner)
    with mock.patch.object(generate_generative_video_task, 'delay',
                           return_value=mock.Mock(id='c-2')) as delay:
        resp = client.post(
            '/api/generate/generative',
            json={'project_id': pid, 'prompt': 'p', 'voice_id': owner_voice},
            headers=owner)
    assert resp.status_code == 202
    delay.assert_called_once()
    _, kwargs = delay.call_args
    assert kwargs['voice_id'] == owner_voice


def test_assembler_without_voice_id_passes_none(client, owner):
    pid = _seed_project(client, owner)
    with mock.patch.object(generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='c-3')) as delay:
        resp = client.post(
            '/api/generate/assembler',
            json={'project_id': pid, 'prompt': 'p'},
            headers=owner)
    assert resp.status_code == 202
    _, kwargs = delay.call_args
    assert kwargs['voice_id'] is None


def test_resolve_owned_voice_helper(client, db_session, owner, owner_voice):
    uid = _user_id(client, owner)
    assert _resolve_owned_voice(db_session, None, uid) == (None, None)
    assert _resolve_owned_voice(db_session, 'nope', uid)[1][1] == 400
    assert _resolve_owned_voice(db_session, 999999, uid)[1][1] == 404
    assert _resolve_owned_voice(db_session, owner_voice, 12345)[1][1] == 403
    v, err = _resolve_owned_voice(db_session, owner_voice, uid)
    assert err is None
    assert v.id == owner_voice