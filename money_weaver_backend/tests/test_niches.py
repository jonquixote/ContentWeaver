from src.services.providers.niche_profile import load, list_niches, inject_prompt


def test_load_tech_niche():
    niche = load("tech")
    assert niche["tone"] == "contrarian"
    assert "hooks" in niche
    assert list_niches() == sorted(list_niches())


def test_inject_appends_hooks():
    niche = {"tone": "urgent", "hooks": ["breaking news"], "forbidden": [], "word_count": 120}
    out = inject_prompt("Write script", niche)
    assert "urgent" in out and "breaking news" in out


def test_api_list_niches(client, auth_headers):
    r = client.get("/api/niches", headers=auth_headers)
    assert r.status_code == 200 and "tech" in r.json()["niches"]
