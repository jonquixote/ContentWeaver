"""Smoke tests for the auth-protected API surface."""


def test_no_token_returns_401(client):
    r = client.get('/api/users/me')
    assert r.status_code == 401


def test_health_route_not_implemented(client):
    # NOTE: there is NO JSON /api/health endpoint. main.py's static catch-all
    # (serve, main.py:123) falls through to the SPA index.html, so the route
    # answers 200 text/html, not 404 and not JSON. Assert that reality: no
    # JSON health payload exists.
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.content_type.startswith('text/html')
    assert not r.is_json