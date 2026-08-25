CATALOG = [
    {"id": "a/text-model", "provider": "openrouter", "display_name": "A Text",
     "capabilities": {"chat": True}, "free": False, "kind": "text"},
    {"id": "b/free-text", "provider": "openrouter", "display_name": "B Free",
     "capabilities": {"chat": True}, "free": True, "kind": "text"},
]


def test_models_filter_kind_and_q(client, auth_headers, monkeypatch):
    from fastapi_app.routers import api_keys
    monkeypatch.setattr(api_keys.registry, 'list_models', lambda force=False: CATALOG)
    r = client.get('/api/models?kind=text&q=free', headers=auth_headers)
    ids = [m['id'] for m in r.json()['models']]
    assert ids == ['b/free-text']


def test_models_filter_kind_video(client, auth_headers, monkeypatch):
    from fastapi_app.routers import api_keys
    monkeypatch.setattr(api_keys.registry, 'list_models', lambda force=False: CATALOG)
    r = client.get('/api/models?kind=video', headers=auth_headers)
    assert r.json()['models'] == []


def test_models_entries_carry_kind(client, auth_headers, monkeypatch):
    from fastapi_app.routers import api_keys
    monkeypatch.setattr(api_keys.registry, 'list_models', lambda force=False: CATALOG)
    r = client.get('/api/models', headers=auth_headers)
    assert all('kind' in m and m['kind'] in ('text', 'voice', 'video')
               for m in r.json()['models'])
