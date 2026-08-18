"""Coverage for the FastAPI media/final file-serving router (auth + Range)."""
import os


def _write(storage_dir, name, content=b'hello world'):
    path = os.path.join(storage_dir, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as fh:
        fh.write(content)
    return path


def test_media_requires_auth(client, storage_dir):
    _write(storage_dir, 'clip.txt')
    r = client.get('/media/clip.txt')
    assert r.status_code == 401


def test_media_serves_file_with_bearer_token(client, auth_headers, storage_dir):
    _write(storage_dir, 'clip.txt', b'hello world')
    r = client.get('/media/clip.txt', headers=auth_headers)
    assert r.status_code == 200
    assert r.content == b'hello world'
    assert r.headers['content-type'].startswith('text/plain')


def test_media_accepts_token_query_param(client, auth_headers, storage_dir):
    _write(storage_dir, 'clip.txt', b'hello')
    token = auth_headers['Authorization'].split(' ', 1)[1]
    r = client.get(f'/media/clip.txt?token={token}')
    assert r.status_code == 200


def test_media_missing_file_is_404(client, auth_headers):
    assert client.get('/media/nope.txt', headers=auth_headers).status_code == 404


def test_media_supports_range_requests(client, auth_headers, storage_dir):
    _write(storage_dir, 'clip.txt', b'0123456789')
    r = client.get('/media/clip.txt', headers={
        **auth_headers, 'Range': 'bytes=0-3'})
    assert r.status_code == 206
    assert r.content == b'0123'
    assert 'Content-Range' in r.headers


def test_media_revoked_token_is_401(client, auth_headers):
    _write(os.environ['STORAGE_LOCAL_DIR'], 'revoked.txt')
    client.post('/api/auth/logout', headers=auth_headers)
    r = client.get('/media/revoked.txt', headers=auth_headers)
    assert r.status_code == 401


def test_final_requires_auth(client, monkeypatch, tmp_path):
    monkeypatch.setattr('fastapi_app.routers.media.FINAL_DIR', str(tmp_path))
    (tmp_path / 'out.mp4').write_bytes(b'MP4')
    assert client.get('/final/out.mp4').status_code == 401


def test_final_serves_video(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr('fastapi_app.routers.media.FINAL_DIR', str(tmp_path))
    (tmp_path / 'out.mp4').write_bytes(b'MP4DATA')
    r = client.get('/final/out.mp4', headers=auth_headers)
    assert r.status_code == 200
    assert r.content == b'MP4DATA'


def test_final_missing_video_is_404(client, auth_headers, monkeypatch, tmp_path):
    monkeypatch.setattr('fastapi_app.routers.media.FINAL_DIR', str(tmp_path))
    assert client.get('/final/nope.mp4', headers=auth_headers).status_code == 404
