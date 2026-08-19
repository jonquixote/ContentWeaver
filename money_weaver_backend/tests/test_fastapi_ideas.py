def test_random_idea(monkeypatch, client, auth_headers):
    monkeypatch.setattr("fastapi_app.routers.ideas.llm_service.generate_idea",
                        lambda seed=None, model=None, language="en": {"title": "T", "topic": "X", "script": "SCENE 1\n..."})
    r = client.post("/api/ideas/random", json={"seed": "space"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["title"] == "T"


def test_random_idea_requires_auth(client):
    assert client.post("/api/ideas/random", json={}).status_code == 401
