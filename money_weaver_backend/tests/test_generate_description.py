def test_description_requires_premise(client, auth_headers):
    r = client.post('/api/generate/description', headers=auth_headers, json={})
    assert r.status_code == 400


def test_description_returns_text(client, auth_headers, monkeypatch):
    from fastapi_app.routers import enhance as enh
    monkeypatch.setattr(enh.llm_service, 'resolve_model_for',
                        lambda uid, task: 'poolside/laguna-s-2.1:free')
    captured = {}
    def fake_chat(user_id, model, messages, **kw):
        captured.update(user_id=user_id, model=model)
        return "A short platform description about coding cats"
    monkeypatch.setattr(enh.llm_service, '_chat_free_resilient', fake_chat)
    r = client.post('/api/generate/description', headers=auth_headers,
                    json={'premise': 'cats learn to code'})
    assert r.status_code == 200
    assert r.json()['description'] == 'A short platform description about coding cats'
    assert captured['model'] == 'poolside/laguna-s-2.1:free'


def test_description_503_on_llm_failure(client, auth_headers, monkeypatch):
    from fastapi_app.routers import enhance as enh
    monkeypatch.setattr(enh.llm_service, 'resolve_model_for',
                        lambda uid, task: 'assigned/m')
    def boom(*args, **kw):
        raise RuntimeError('no provider configured')
    monkeypatch.setattr(enh.llm_service, '_chat_free_resilient', boom)
    r = client.post('/api/generate/description', headers=auth_headers,
                    json={'premise': 'cats learn to code'})
    assert r.status_code == 503