def test_enhance_uses_assignment_and_returns_text(client, auth_headers, monkeypatch):
    from fastapi_app.routers import enhance as enh
    monkeypatch.setattr(enh.llm_service, 'resolve_model_for',
                        lambda uid, task: 'poolside/laguna-s-2.1:free')
    captured = {}
    def fake_chat(user_id, model, messages, **kw):
        captured.update(user_id=user_id, model=model)
        return "A better prompt about volcanoes"
    monkeypatch.setattr(enh.llm_service, '_chat_free_resilient', fake_chat)
    r = client.post('/api/enhance-prompt', headers=auth_headers,
                    json={'text': 'volcano video'})
    assert r.status_code == 200
    assert r.json()['enhanced'] == 'A better prompt about volcanoes'
    assert captured['model'] == 'poolside/laguna-s-2.1:free'


def test_enhance_requires_text(client, auth_headers):
    assert client.post('/api/enhance-prompt', headers=auth_headers,
                       json={'text': '  '}).status_code == 400


def test_draft_script_returns_screenplay(client, auth_headers, monkeypatch):
    from fastapi_app.routers import enhance as enh
    monkeypatch.setattr(enh.llm_service, 'resolve_model_for',
                        lambda uid, task: {'script': 'assigned/m'}.get(task))
    seen = {}
    monkeypatch.setattr(enh.llm_service, 'generate_script',
                        lambda prompt, uid, model=None, **kw:
                        seen.update(model=model, uid=uid) or "SCENE 1: X\nEND")
    r = client.post('/api/scripts/draft', headers=auth_headers,
                    json={'topic': 'volcanoes', 'duration': 30})
    assert r.status_code == 200
    assert 'SCENE 1' in r.json()['script']
    assert seen['model'] == 'assigned/m'


def test_draft_rejects_blank_topic(client, auth_headers):
    assert client.post('/api/scripts/draft', headers=auth_headers,
                       json={'topic': ''}).status_code == 400
