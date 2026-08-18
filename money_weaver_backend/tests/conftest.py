import os
import tempfile

import pytest

# MUST be set at module top, BEFORE any `import fastapi_app` (or src packages
# that read these at import time: fastapi_app/db.py creates the engine,
# fastapi_app/routers/media.py reads STORAGE_LOCAL_DIR, local storage provider
# reads STORAGE_LOCAL_DIR). A temp FILE db (not :memory:) is required so that
# task bodies run via create_app_context() open their own connections against
# the same shared sqlite file.
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['DATABASE_URL'] = f"sqlite:///{tempfile.mkdtemp(prefix='mw-pytest-')}/test.db"
os.environ['STORAGE_BACKEND'] = 'local'
os.environ['STORAGE_LOCAL_DIR'] = tempfile.mkdtemp(prefix='mw-uploads-')


# Kept in sync with fastapi_app/main.py SEED_PRESETS (the lifespan seeds these
# exactly once per TestClient session; teardown's drop_all wipes them, so the
# lifespan re-seeds on the next test).
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
    from fastapi_app.main import app
    return app


@pytest.fixture()
def client(app):
    from fastapi_app.db import engine
    from src.database import db
    from starlette.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
        db.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(client):
    from fastapi_app.db import db_session as _session_cm
    with _session_cm() as session:
        yield session


@pytest.fixture()
def storage_dir():
    return os.environ['STORAGE_LOCAL_DIR']


@pytest.fixture()
def auth_headers(client):
    client.post('/api/auth/register', json={
        'email': 'test@test.com', 'username': 'tester', 'password': 'password123'})
    r = client.post('/api/auth/login', json={
        'email': 'test@test.com', 'password': 'password123'})
    token = r.json()['token']
    return {'Authorization': f'Bearer {token}'}
