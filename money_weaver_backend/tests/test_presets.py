"""Route tests for GET /api/presets (auth-protected, seeded format presets).

Seeding is handled by src/main.py (import time) plus the conftest `app`
fixture, which re-seeds the 6 rows after each drop_all teardown.
"""

REQUIRED_PRESET_FIELDS = {
    'id', 'name', 'platform', 'width', 'height',
    'fps', 'duration_min', 'duration_max', 'is_default',
}


def test_presets_seeded(client, auth_headers):
    r = client.get('/api/presets', headers=auth_headers)
    assert r.status_code == 200
    data = r.get_json()
    assert len(data) == 6
    for preset in data:
        assert set(preset.keys()) == REQUIRED_PRESET_FIELDS
        assert isinstance(preset['id'], int)
        assert isinstance(preset['name'], str) and preset['name']
        assert isinstance(preset['platform'], str) and preset['platform']
        assert isinstance(preset['width'], int) and preset['width'] > 0
        assert isinstance(preset['height'], int) and preset['height'] > 0
        assert isinstance(preset['fps'], int) and preset['fps'] > 0
        assert isinstance(preset['duration_min'], int) and preset['duration_min'] > 0
        assert isinstance(preset['duration_max'], int)
        assert preset['duration_min'] <= preset['duration_max']


def test_presets_have_exactly_one_default(client, auth_headers):
    r = client.get('/api/presets', headers=auth_headers)
    assert r.status_code == 200
    defaults = [p for p in r.get_json() if p['is_default']]
    assert len(defaults) == 1
    assert defaults[0]['platform'] == 'youtube'


def test_presets_require_auth(client):
    assert client.get('/api/presets').status_code == 401
