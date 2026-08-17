import os
import tempfile

import pytest

# MUST be set at module top, BEFORE any `import src.main`.
# main.py load_dotenv() does NOT override existing env vars, so these win over .env.
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['DATABASE_URL'] = f"sqlite:///{tempfile.mkdtemp(prefix='mw-pytest-')}/test.db"
os.environ['STORAGE_BACKEND'] = 'local'
os.environ['STORAGE_LOCAL_DIR'] = tempfile.mkdtemp(prefix='mw-uploads-')


# main.py:89-101 seeds presets INLINE (not factored into a function), so replicate
# the exact rows here. Keep in sync with main.py's SEED_PRESETS.
_SEED_PRESETS = [
    ('YouTube Landscape', 'youtube', 1920, 1080, 30, 60, 600, True),
    ('YouTube Shorts', 'shorts', 1080, 1920, 30, 15, 60, False),
    ('TikTok', 'tiktok', 1080, 1920, 30, 15, 60, False),
    ('Instagram Reels', 'reels', 1080, 1920, 30, 15, 60, False),
    ('Instagram Square', 'instagram', 1080, 1080, 30, 15, 60, False),
    ('Twitter/X', 'twitter', 1280, 720, 30, 15, 60, False),
]


@pytest.fixture()
def app():
    from src.main import app, db
    from src.models.preset import FormatPreset

    with app.app_context():
        db.create_all()
        # main.py seeds at import time; teardown's drop_all below wipes presets,
        # so re-seed here to keep the preset count at 6 for every test.
        if FormatPreset.query.count() == 0:
            for name, platform, w, h, fps, dmin, dmax, is_def in _SEED_PRESETS:
                db.session.add(FormatPreset(name=name, platform=platform, width=w, height=h,
                                            fps=fps, duration_min=dmin, duration_max=dmax,
                                            is_default=is_def))
            db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth_headers(client):
    client.post('/api/auth/register', json={
        'email': 'test@test.com', 'username': 'tester', 'password': 'password123'})
    r = client.post('/api/auth/login', json={
        'email': 'test@test.com', 'password': 'password123'})
    token = r.get_json()['token']
    return {'Authorization': f'Bearer {token}'}