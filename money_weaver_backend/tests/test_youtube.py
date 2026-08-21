"""Tests for YouTube private upload + OAuth + webhooks (Task 8).

All google-api-python-client / google-auth-oauthlib interactions are mocked
via the uploader's lazy-import seams — no network, no real Google libraries
required (they are not installed in this venv).
"""
import hashlib
import hmac
import json
import os
import stat
import sys
import tempfile
import types
from unittest import mock

import pytest

from src.services.providers import youtube_uploader


# ---------------------------------------------------------------------------
# Shared fakes / helpers
# ---------------------------------------------------------------------------

CAPTURED = {}


class FakeInsertRequest:
    """Stands in for the resumable videos().insert request."""

    def __init__(self, response):
        self._response = response

    def next_chunk(self):
        return None, self._response


class FakeVideos:
    def insert(self, **kwargs):
        CAPTURED['video_insert'] = kwargs
        return FakeInsertRequest(CAPTURED.setdefault('video_response', {'id': 'abc123'}))


class FakeCaptions:
    def insert(self, **kwargs):
        CAPTURED['caption_insert'] = kwargs
        return types.SimpleNamespace(execute=lambda: {'id': 'cap1'})


class FakeYouTube:
    def videos(self):
        return FakeVideos()

    def captions(self):
        return FakeCaptions()


class FakeCredentials:
    def __init__(self, marker='creds-sentinel'):
        self.marker = marker

    @classmethod
    def from_authorized_user_file(cls, path, scopes):
        CAPTURED['cred_file'] = path
        CAPTURED['cred_scopes'] = tuple(scopes)
        return cls()

    def to_json(self):
        return json.dumps({'marker': self.marker})


class FakeFlow:
    instances = []

    def __init__(self):
        self.redirect_uri = None
        self.fetched_code = None
        self.credentials = FakeCredentials()
        type(self).instances.append(self)

    @classmethod
    def from_client_secrets_file(cls, path, scopes):
        CAPTURED['flow_secret'] = path
        CAPTURED['flow_scopes'] = tuple(scopes)
        return cls()

    def authorization_url(self, **kwargs):
        CAPTURED['auth_url_kwargs'] = kwargs
        return 'https://accounts.google.com/o/oauth2/auth?fake=1', None

    def fetch_token(self, code=None):
        self.fetched_code = code


def _reset():
    CAPTURED.clear()


@pytest.fixture()
def clean_captured():
    _reset()
    yield CAPTURED
    _reset()


def _db_project(tmp_path, monkeypatch, *, video_url=None, title='yt project'):
    """Create a real Project row in a throwaway sqlite db (test_viral pattern)."""
    os.environ.setdefault('SECRET_KEY', 'test-secret-key')
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path}/yt_test.db')
    vt = pytest.importorskip('src.tasks.video_tasks')
    from src.database import db

    app = vt.create_app_context()
    with app.app_context():
        db.create_all()
        from src.models.project import Project
        from src.models.user import User

        user = User(username='yt-owner', email='yt-owner@t.com', password_hash='x')
        db.session.add(user)
        db.session.flush()
        project = Project(title=title, description='desc', user_id=user.id,
                          voice_type='female', status='completed',
                          video_url=video_url)
        db.session.add(project)
        db.session.commit()
        return app, project.id, user.id


# ---------------------------------------------------------------------------
# get_auth_url / handle_callback (OAuth)
# ---------------------------------------------------------------------------

def test_get_auth_url_returns_authorization_url(tmp_path, monkeypatch, clean_captured):
    secret = tmp_path / 'client_secret.json'
    secret.write_text('{}')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET_FILE', str(secret))
    monkeypatch.setattr(youtube_uploader, '_flow_class', lambda: FakeFlow)
    url = youtube_uploader.get_auth_url(42)
    assert url.startswith('https://accounts.google.com/o/oauth2/auth')
    assert youtube_uploader.SCOPES == ('https://www.googleapis.com/auth/youtube.upload',)
    assert CAPTURED['flow_scopes'] == youtube_uploader.SCOPES


def test_get_auth_url_sets_redirect_uri_from_env(tmp_path, monkeypatch, clean_captured):
    secret = tmp_path / 'client_secret.json'
    secret.write_text('{}')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET_FILE', str(secret))
    monkeypatch.setenv('YOUTUBE_OAUTH_REDIRECT_URI', 'http://example.com/cb')
    holder = {}

    class SpyFlow(FakeFlow):
        def authorization_url(self, **kwargs):
            holder['redirect'] = self.redirect_uri
            return 'u', None

    monkeypatch.setattr(youtube_uploader, '_flow_class', lambda: SpyFlow)
    youtube_uploader.get_auth_url(1)
    assert holder['redirect'] == 'http://example.com/cb'


def test_get_auth_url_missing_client_secret_raises(tmp_path, monkeypatch):
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET_FILE', str(tmp_path / 'missing.json'))
    with pytest.raises(RuntimeError, match='client secret'):
        youtube_uploader.get_auth_url(1)


def test_handle_callback_saves_token_0600(tmp_path, monkeypatch, clean_captured):
    secret = tmp_path / 'client_secret.json'
    secret.write_text('{}')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET_FILE', str(secret))
    monkeypatch.setattr(youtube_uploader, '_flow_class', lambda: FakeFlow)
    monkeypatch.setattr(youtube_uploader, 'token_dir', lambda: str(tmp_path / 'tokens'))

    path = youtube_uploader.handle_callback('the-code', 7)

    flow = FakeFlow.instances[-1]
    assert flow.fetched_code == 'the-code'
    assert path.endswith('token_7.json')
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600
    assert json.loads(open(path).read())['marker'] == 'creds-sentinel'


def test_lazy_import_missing_lib_raises_clear_error(tmp_path, monkeypatch):
    """Absence of google libs surfaces a readable message, not ImportError."""
    secret = tmp_path / 'client_secret.json'
    secret.write_text('{}')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET_FILE', str(secret))
    monkeypatch.setitem(sys.modules, 'google_auth_oauthlib.flow', None)
    with pytest.raises(RuntimeError, match='google-auth-oauthlib'):
        youtube_uploader.get_auth_url(1)


# ---------------------------------------------------------------------------
# upload_video
# ---------------------------------------------------------------------------

def _mock_google(monkeypatch, tmp_path, response_id='abc123'):
    monkeypatch.setattr(youtube_uploader, 'token_dir', lambda: str(tmp_path / 'tokens'))
    os.makedirs(tmp_path / 'tokens', exist_ok=True)
    (tmp_path / 'tokens' / 'token_1.json').write_text('{}')
    monkeypatch.setattr(youtube_uploader, '_load_credentials', lambda uid: FakeCredentials())
    monkeypatch.setattr(youtube_uploader, '_build', lambda creds: FakeYouTube())
    CAPTURED['video_response'] = {'id': response_id}
    media_paths = []

    def fake_media(path, **kwargs):
        media_paths.append(path)
        if str(path).endswith('.srt'):
            # uploader unlinks the temp srt right after insert; snapshot now
            CAPTURED['srt_content'] = open(path).read()
        return mock.Mock(name='media')

    CAPTURED['media_paths'] = media_paths
    monkeypatch.setattr(youtube_uploader, '_media_upload_cls', lambda: fake_media)


def test_upload_video_mocked_happy_path(tmp_path, monkeypatch, clean_captured):
    app, pid, uid = _db_project(tmp_path, monkeypatch)
    video = tmp_path / 'render.mp4'
    video.write_bytes(b'\x00\x00\x00\x18ftypmp42')
    _mock_google(monkeypatch, tmp_path)

    with app.app_context():
        result = youtube_uploader.upload_video(pid, video_path=str(video))

    assert result == {'youtube_url': 'https://youtu.be/abc123', 'video_id': 'abc123'}
    insert = CAPTURED['video_insert']
    assert insert['body']['status']['privacyStatus'] == 'private'
    assert insert['part'] == 'snippet,status'


def test_upload_video_respects_privacy_override(tmp_path, monkeypatch, clean_captured):
    app, pid, uid = _db_project(tmp_path, monkeypatch)
    video = tmp_path / 'render.mp4'
    video.write_bytes(b'x')
    _mock_google(monkeypatch, tmp_path)

    with app.app_context():
        youtube_uploader.upload_video(pid, privacy='unlisted', video_path=str(video))

    assert CAPTURED['video_insert']['body']['status']['privacyStatus'] == 'unlisted'


def test_upload_video_without_token_raises(tmp_path, monkeypatch):
    app, pid, uid = _db_project(tmp_path, monkeypatch)
    monkeypatch.setattr(youtube_uploader, 'token_dir', lambda: str(tmp_path / 'nope'))
    with app.app_context(), pytest.raises(RuntimeError, match='OAuth'):
        youtube_uploader.upload_video(pid)


def test_upload_video_uploads_srt_caption_sidecar(tmp_path, monkeypatch, clean_captured):
    app, pid, uid = _db_project(tmp_path, monkeypatch)
    video = tmp_path / 'render.mp4'
    video.write_bytes(b'x')
    _mock_google(monkeypatch, tmp_path)
    transcript = [{'word': 'wow', 'start': 0, 'end': 1}]

    with app.app_context():
        youtube_uploader.upload_video(pid, video_path=str(video), transcript=transcript)

    assert 'caption_insert' in CAPTURED
    assert CAPTURED['caption_insert']['body']['snippet']['videoId'] == 'abc123'
    assert '-->' in CAPTURED['srt_content']
    assert 'wow' in CAPTURED['srt_content']


def test_upload_video_no_transcript_skips_captions(tmp_path, monkeypatch, clean_captured):
    app, pid, uid = _db_project(tmp_path, monkeypatch)
    video = tmp_path / 'render.mp4'
    video.write_bytes(b'x')
    _mock_google(monkeypatch, tmp_path)

    with app.app_context():
        youtube_uploader.upload_video(pid, video_path=str(video))

    assert 'caption_insert' not in CAPTURED


def test_upload_video_missing_project_raises(tmp_path, monkeypatch):
    app, pid, uid = _db_project(tmp_path, monkeypatch)
    with app.app_context(), pytest.raises(RuntimeError, match='not found'):
        youtube_uploader.upload_video(99999)


# ---------------------------------------------------------------------------
# Webhook signing (hmac_sha256 over exact body)
# ---------------------------------------------------------------------------

def _capture_httpx(monkeypatch):
    calls = []
    fake_httpx = types.ModuleType('httpx')

    def fake_post(url, content=None, headers=None, timeout=None):
        calls.append({'url': url, 'content': content, 'headers': headers})
        return mock.Mock(status_code=200)

    fake_httpx.post = fake_post
    monkeypatch.setitem(sys.modules, 'httpx', fake_httpx)
    return calls


def test_send_webhook_signs_body_with_hmac(monkeypatch):
    from src.tasks.video_tasks import send_webhook
    calls = _capture_httpx(monkeypatch)

    send_webhook('https://hooks.example/x', 's3cret', {'event': 'done', 'ok': True})

    body = calls[0]['content']
    expected = hmac.new(b's3cret', body.encode(), hashlib.sha256).hexdigest()
    assert calls[0]['headers']['X-Signature'] == expected
    assert json.loads(body)['event'] == 'done'


def test_send_webhook_different_secret_different_signature(monkeypatch):
    from src.tasks.video_tasks import send_webhook
    calls = _capture_httpx(monkeypatch)

    send_webhook('https://hooks.example/x', 'right', {'a': 1})
    good = calls[0]['headers']['X-Signature']
    bad = hmac.new(b'wrong', calls[0]['content'].encode(), hashlib.sha256).hexdigest()
    assert good != bad


def test_send_webhook_noop_without_url(monkeypatch):
    from src.tasks.video_tasks import send_webhook
    calls = _capture_httpx(monkeypatch)
    send_webhook(None, 's3cret', {'a': 1})
    assert calls == []


def test_send_webhook_delivery_failure_never_raises(monkeypatch):
    from src.tasks.video_tasks import send_webhook
    fake_httpx = types.ModuleType('httpx')
    fake_httpx.post = mock.Mock(side_effect=RuntimeError('network down'))
    monkeypatch.setitem(sys.modules, 'httpx', fake_httpx)
    send_webhook('https://hooks.example/x', 's3cret', {'a': 1})


# ---------------------------------------------------------------------------
# Router: /api/youtube/*
# ---------------------------------------------------------------------------

def _create_project(client, headers):
    r = client.post('/api/projects', json={'title': 'yt project'}, headers=headers)
    assert r.status_code == 201
    return r.json()['id']


def test_youtube_upload_enqueues_202(client, auth_headers):
    pid = _create_project(client, auth_headers)
    from fastapi_app.routers import youtube as youtube_router
    with mock.patch.object(youtube_router.youtube_upload_task, 'delay',
                           return_value=mock.Mock(id='cel-yt-1')) as delay:
        r = client.post('/api/youtube/upload',
                        json={'project_id': pid}, headers=auth_headers)
    assert r.status_code == 202
    body = r.json()
    assert body['celery_task_id'] == 'cel-yt-1'
    assert body['project_id'] == pid
    assert delay.call_args.kwargs['privacy'] == 'private'


def test_youtube_upload_rejects_bad_privacy(client, auth_headers):
    pid = _create_project(client, auth_headers)
    r = client.post('/api/youtube/upload',
                    json={'project_id': pid, 'privacy': 'weird'},
                    headers=auth_headers)
    assert r.status_code == 400


def test_youtube_upload_requires_auth(client):
    assert client.post('/api/youtube/upload',
                       json={'project_id': 1}).status_code == 401


def test_youtube_upload_foreign_project_is_403(client, auth_headers):
    client.post('/api/auth/register', json={
        'email': 'yt-other@test.com', 'username': 'ytother',
        'password': 'password123'})
    other = client.post('/api/auth/login', json={
        'email': 'yt-other@test.com', 'password': 'password123'}).json()['token']
    other_headers = {'Authorization': f'Bearer {other}'}
    pid = _create_project(client, auth_headers)
    r = client.post('/api/youtube/upload',
                    json={'project_id': pid}, headers=other_headers)
    assert r.status_code == 403


def test_youtube_upload_nonexistent_project_is_404(client, auth_headers):
    r = client.post('/api/youtube/upload',
                    json={'project_id': 9999}, headers=auth_headers)
    assert r.status_code == 404


def test_youtube_upload_queue_unavailable_is_503(client, auth_headers):
    pid = _create_project(client, auth_headers)
    from fastapi_app.routers import youtube as youtube_router
    with mock.patch.object(youtube_router.youtube_upload_task, 'delay',
                           side_effect=RuntimeError('redis down')):
        r = client.post('/api/youtube/upload',
                        json={'project_id': pid}, headers=auth_headers)
    assert r.status_code == 503


def test_youtube_auth_url_returns_url(client, auth_headers, monkeypatch):
    monkeypatch.setattr(youtube_uploader, 'get_auth_url',
                        lambda uid: 'https://accounts.google.com/o/oauth2/auth?x')
    r = client.get('/api/youtube/auth-url', headers=auth_headers)
    assert r.status_code == 200
    assert r.json()['url'].startswith('https://accounts.google.com/')


def test_youtube_auth_url_requires_auth(client):
    assert client.get('/api/youtube/auth-url').status_code == 401


def test_youtube_auth_url_config_problem_is_503(client, auth_headers, monkeypatch):
    monkeypatch.setattr(youtube_uploader, 'get_auth_url',
                        mock.Mock(side_effect=RuntimeError('client secret not found')))
    r = client.get('/api/youtube/auth-url', headers=auth_headers)
    assert r.status_code == 503


def test_youtube_callback_connects_account(client, auth_headers, db_session, monkeypatch):
    from src.models.user import User
    user = db_session.query(User).filter_by(email='test@test.com').first()
    seen = {}

    def fake_handle(code, uid):
        seen.update(code=code, uid=uid)
        return f'/tokens/token_{uid}.json'

    monkeypatch.setattr(youtube_uploader, 'handle_callback', fake_handle)
    r = client.get('/api/youtube/callback',
                   params={'code': 'oauth-code', 'state': user.id})
    assert r.status_code == 200
    assert seen == {'code': 'oauth-code', 'uid': user.id}


def test_youtube_callback_unknown_state_rejected(client, monkeypatch):
    monkeypatch.setattr(youtube_uploader, 'handle_callback',
                        mock.Mock(return_value='/x'))
    r = client.get('/api/youtube/callback',
                   params={'code': 'c', 'state': 424242})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Router: /api/generate/assembler webhooks
# ---------------------------------------------------------------------------

def test_assembler_webhook_requires_secret(client, auth_headers):
    pid = _create_project(client, auth_headers)
    r = client.post('/api/generate/assembler',
                    json={'project_id': pid, 'prompt': 'p',
                          'webhook_url': 'https://hooks.example/x'},
                    headers=auth_headers)
    assert r.status_code == 400
    assert 'webhook_secret' in r.json()['error']


def test_assembler_webhook_passes_url_and_secret_to_task(client, auth_headers):
    pid = _create_project(client, auth_headers)
    from fastapi_app.routers import generation
    with mock.patch.object(generation.generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='cel-wh-1')) as delay:
        r = client.post('/api/generate/assembler',
                        json={'project_id': pid, 'prompt': 'p',
                              'webhook_url': 'https://hooks.example/x',
                              'webhook_secret': 's3cret'},
                        headers=auth_headers)
    assert r.status_code == 202
    kwargs = delay.call_args.kwargs
    assert kwargs['webhook_url'] == 'https://hooks.example/x'
    assert kwargs['webhook_secret'] == 's3cret'


def test_assembler_without_webhook_defaults_none(client, auth_headers):
    """Backward compat: omitting webhook fields still enqueues unchanged."""
    pid = _create_project(client, auth_headers)
    from fastapi_app.routers import generation
    with mock.patch.object(generation.generate_assembler_video_task, 'delay',
                           return_value=mock.Mock(id='cel-wh-2')) as delay:
        r = client.post('/api/generate/assembler',
                        json={'project_id': pid, 'prompt': 'p'},
                        headers=auth_headers)
    assert r.status_code == 202
    kwargs = delay.call_args.kwargs
    assert kwargs['webhook_url'] is None
    assert kwargs['webhook_secret'] is None


# ---------------------------------------------------------------------------
# Celery task: youtube_upload_task
# ---------------------------------------------------------------------------

class _FakeTaskSelf:
    def __init__(self, tid='fake-yt-celery-id'):
        self.request = types.SimpleNamespace(id=tid)

    def update_state(self, *args, **kwargs):
        pass


def test_youtube_upload_task_completes_and_records_result(tmp_path, monkeypatch):
    app, pid, uid = _db_project(tmp_path, monkeypatch, video_url='videos/u/p/v.mp4')
    vt = pytest.importorskip('src.tasks.video_tasks')
    from src.database import db
    from src.models.task import Task

    record = Task(project_id=pid, task_type='youtube_upload', status='pending',
                  celery_task_id='fake-yt-celery-id')
    with app.app_context():
        db.session.add(record)
        db.session.commit()

    class FakeStorage:
        def get_object(self, key):
            return b'\x00\x00\x00\x18ftypmp42'

    monkeypatch.setattr(vt, 'get_storage', lambda: FakeStorage())

    video_blob = {}

    def fake_upload(project_id, privacy='private', video_path=None, transcript=None):
        video_blob['path'] = video_path
        assert open(video_path, 'rb').read() == b'\x00\x00\x00\x18ftypmp42'
        return {'youtube_url': 'https://youtu.be/xyz789', 'video_id': 'xyz789'}

    monkeypatch.setattr(youtube_uploader, 'upload_video', fake_upload)

    out = vt.youtube_upload_task.run.__func__(_FakeTaskSelf(), pid)

    assert out['result']['video_id'] == 'xyz789'
    with app.app_context():
        done = vt.find_task_record('fake-yt-celery-id', pid, 'youtube_upload')
        assert done.status == 'completed'
        assert json.loads(done.result)['video_id'] == 'xyz789'
    # materialized temp copy cleaned up
    leftovers = [f for f in os.listdir(tempfile.gettempdir())
                 if f.startswith(f'yt_{pid}_')]
    assert leftovers == []


def test_youtube_upload_task_failure_records_error(tmp_path, monkeypatch):
    app, pid, uid = _db_project(tmp_path, monkeypatch, video_url='videos/u/p/v.mp4')
    vt = pytest.importorskip('src.tasks.video_tasks')
    from src.database import db
    from src.models.task import Task

    record = Task(project_id=pid, task_type='youtube_upload', status='pending',
                  celery_task_id='fake-yt-fail-id')
    with app.app_context():
        db.session.add(record)
        db.session.commit()

    class FakeStorage:
        def get_object(self, key):
            return b'data'

    monkeypatch.setattr(vt, 'get_storage', lambda: FakeStorage())
    monkeypatch.setattr(
        youtube_uploader, 'upload_video',
        mock.Mock(side_effect=RuntimeError('quota exceeded')))

    with app.app_context():
        with pytest.raises(RuntimeError, match='quota exceeded'):
            vt.youtube_upload_task.run.__func__(_FakeTaskSelf('fake-yt-fail-id'), pid)
        failed = vt.find_task_record('fake-yt-fail-id', pid, 'youtube_upload')
        assert failed.status == 'failed'
        assert 'quota exceeded' in (failed.error_message or '')
