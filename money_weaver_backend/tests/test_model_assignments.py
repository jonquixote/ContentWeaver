VALID_TASKS = {"idea", "script", "enhance", "voice_tts", "video_gen"}


def test_put_and_get_assignments(client, auth_headers):
    r = client.put('/api/model-assignments', headers=auth_headers,
                   json={"assignments": {"idea": "poolside/laguna-s-2.1:free",
                                         "video_gen": "fal-ai/wan-t2v"}})
    assert r.status_code == 200
    r = client.get('/api/model-assignments', headers=auth_headers)
    assert r.status_code == 200
    a = r.json()['assignments']
    assert a['idea'] == 'poolside/laguna-s-2.1:free'
    assert a['video_gen'] == 'fal-ai/wan-t2v'


def test_put_rejects_unknown_task(client, auth_headers):
    r = client.put('/api/model-assignments', headers=auth_headers,
                   json={"assignments": {"bogus_task": "x"}})
    assert r.status_code == 400


def test_resolve_precedence_assignment_over_prefs(client, auth_headers, db_session):
    from src.services.llm_service import resolve_model_for
    from src.models.model_assignment import ModelAssignment
    from src.models.model_preference import ModelPreference
    uid = client.get('/api/users/me', headers=auth_headers).json()['id']
    db_session.add(ModelAssignment(user_id=uid, task='script', model_id='assigned/model'))
    db_session.add(ModelPreference(user_id=uid, defaults='{"script": "pref/model"}',
                                   fallbacks='[]'))
    db_session.commit()
    assert resolve_model_for(uid, 'script') == 'assigned/model'


def test_resolve_falls_back_to_prefs_then_default(client, auth_headers, db_session, monkeypatch):
    from src.services.llm_service import resolve_model_for
    from src.models.model_preference import ModelPreference
    from src.services.providers import registry as reg_mod
    uid = client.get('/api/users/me', headers=auth_headers).json()['id']
    db_session.add(ModelPreference(user_id=uid, defaults='{"script": "pref/model"}',
                                   fallbacks='[]'))
    db_session.commit()
    monkeypatch.setattr(reg_mod.registry, 'best_free',
                        lambda capability='chat': 'poolside/laguna-s-2.1:free')
    assert resolve_model_for(uid, 'script') == 'pref/model'
    assert resolve_model_for(uid, 'enhance') == 'poolside/laguna-s-2.1:free'


def test_resolve_voice_video_defaults():
    from src.services.llm_service import resolve_model_for
    import os
    from unittest import mock
    with mock.patch.dict(os.environ, {'COMFY_ENABLED': ''}):
        assert resolve_model_for(None, 'voice_tts') == 'auto'
        assert resolve_model_for(None, 'video_gen').startswith('fal-ai/')


def test_resolve_unknown_task_raises():
    from src.services.llm_service import resolve_model_for
    import pytest
    with pytest.raises(ValueError):
        resolve_model_for(None, 'bogus')
