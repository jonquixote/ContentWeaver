def test_models_returns_list(client, auth_headers, monkeypatch):
    monkeypatch.setattr("fastapi_app.routers.api_keys.registry.list_models",
                        lambda force=False: [{"id": "openrouter/free", "provider": "openrouter",
                                              "display_name": "r", "capabilities": {"chat": True},
                                              "free": True, "context_window": 1000}])
    r = client.get("/api/models", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["models"][0]["free"] is True


def test_settings_defaults_put_get(client, auth_headers):
    r = client.put("/api/settings/models", json={"defaults": {"script": "a/default"},
                                                 "fallbacks": ["a/fallback"]}, headers=auth_headers)
    assert r.status_code == 200
    r = client.get("/api/settings/models", headers=auth_headers)
    assert r.json()["defaults"]["script"] == "a/default"


def test_settings_requires_auth(client):
    assert client.get("/api/settings/models").status_code == 401
