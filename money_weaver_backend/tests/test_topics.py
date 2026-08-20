from src.services import topic_service


def test_fetch_topics_mocked(monkeypatch, client, auth_headers):
    monkeypatch.setattr(
        topic_service, "fetch_reddit",
        lambda n, l: [{"title": "Test", "source": "reddit", "url": "https://r.com"}])
    monkeypatch.setattr(topic_service, "fetch_rss", lambda n, l: [])
    monkeypatch.setattr(topic_service, "fetch_trends", lambda n, l: [])
    r = client.get("/api/topics?niche=tech&limit=5", headers=auth_headers)
    assert r.status_code == 200 and len(r.json()["topics"]) >= 1
    assert r.json()["topics"][0]["title"] == "Test"


def test_fetch_topics_dedup_and_limit(monkeypatch):
    monkeypatch.setattr(
        topic_service, "fetch_reddit",
        lambda n, l: [
            {"title": "A", "source": "reddit", "url": "https://r.com/a"},
            {"title": "B", "source": "reddit", "url": "https://r.com/b"},
        ])
    monkeypatch.setattr(
        topic_service, "fetch_rss",
        lambda n, l: [
            {"title": "B", "source": "rss", "url": "https://x.com/b"},
            {"title": "C", "source": "rss", "url": "https://x.com/c"},
        ])
    out = topic_service.fetch_topics("tech", limit=2)
    assert [t["title"] for t in out] == ["A", "B"]


def test_gather_research_truncates_300():
    assert len(topic_service.gather_research("x" * 400)) == 300