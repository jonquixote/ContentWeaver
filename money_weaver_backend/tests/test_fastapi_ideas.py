def test_random_idea(monkeypatch, client, auth_headers):
    monkeypatch.setattr("fastapi_app.routers.ideas.llm_service.generate_idea",
                        lambda seed=None, model=None, language="en", user_id=None: {"title": "T", "topic": "X", "script": "SCENE 1\n..."})
    r = client.post("/api/ideas/random", json={"seed": "space"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["title"] == "T"


def test_random_idea_honors_body_model(monkeypatch, client, auth_headers):
    """Wizard override: body['model'] must reach generate_idea verbatim,
    bypassing pick_model."""
    from unittest import mock
    import fastapi_app.routers.ideas as ideas_router
    captured = {}

    def fake_generate_idea(seed=None, model=None, language="en", user_id=None):
        captured.update(seed=seed, model=model, user_id=user_id)
        return {"title": "T", "topic": "X", "script": "SCENE 1\n..."}

    monkeypatch.setattr(ideas_router.llm_service, "generate_idea",
                        fake_generate_idea)
    pick_spy = mock.Mock(return_value="registry/picked")
    monkeypatch.setattr(ideas_router.llm_service, "pick_model", pick_spy)

    r = client.post("/api/ideas/random",
                    json={"seed": "space", "model": "openai/gpt-4o-mini"},
                    headers=auth_headers)
    assert r.status_code == 200
    assert captured["model"] == "openai/gpt-4o-mini"
    pick_spy.assert_not_called()


def test_random_idea_falls_back_to_pick_model(monkeypatch, client, auth_headers):
    """No body['model'] -> registry pick_model path still used."""
    import fastapi_app.routers.ideas as ideas_router
    captured = {}
    monkeypatch.setattr(ideas_router.llm_service, "generate_idea",
                        lambda seed=None, model=None, language="en", user_id=None:
                        (captured.update(model=model), {"title": "T"})[1])
    monkeypatch.setattr(ideas_router.llm_service, "pick_model",
                        lambda uid, prefs, task: "registry/picked")
    r = client.post("/api/ideas/random", json={"seed": "space"}, headers=auth_headers)
    assert r.status_code == 200
    assert captured["model"] == "registry/picked"


def test_random_idea_requires_auth(client):
    assert client.post("/api/ideas/random", json={}).status_code == 401
