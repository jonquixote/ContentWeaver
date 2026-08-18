"""Coverage for the FastAPI /api/uploads presign + PUT router."""
from fastapi_app.routers import uploads


def _uid(client, auth_headers):
    return client.get('/api/users/me', headers=auth_headers).json()['id']


def test_presign_wav(client, auth_headers):
    r = client.get('/api/uploads/presign?ext=wav', headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body['upload_url']
    assert body['object_key'].startswith(f'voices/{_uid(client, auth_headers)}/')


def test_presign_mp3(client, auth_headers):
    r = client.get('/api/uploads/presign?ext=mp3', headers=auth_headers)
    assert r.status_code == 200
    assert r.json()['object_key'].endswith('.mp3')


def test_presign_bad_ext_is_400(client, auth_headers):
    assert client.get('/api/uploads/presign?ext=exe',
                      headers=auth_headers).status_code == 400
    assert client.get('/api/uploads/presign', headers=auth_headers).status_code == 400


def test_put_upload_happy_path(client, auth_headers):
    key = client.get('/api/uploads/presign?ext=wav',
                     headers=auth_headers).json()['object_key']
    r = client.put(f'/api/uploads/{key}', headers=auth_headers, data=b'RIFF')
    assert r.status_code == 200
    assert r.json() == {'ok': True, 'object_key': key}


def test_put_upload_invalid_key_is_400(client, auth_headers):
    r = client.put('/api/uploads/voices/9999/foo.wav',
                   headers=auth_headers, data=b'RIFF')
    assert r.status_code == 400
    assert client.put('/api/uploads/videos/x.mp4',
                      headers=auth_headers, data=b'x').status_code == 400


def test_put_upload_empty_body_is_400(client, auth_headers):
    key = client.get('/api/uploads/presign?ext=wav',
                     headers=auth_headers).json()['object_key']
    assert client.put(f'/api/uploads/{key}', headers=auth_headers,
                      data=b'').status_code == 400


def test_put_upload_oversized_content_length_is_413(client, auth_headers, monkeypatch):
    monkeypatch.setattr('fastapi_app.routers.uploads.MAX_UPLOAD_BYTES', 10)
    key = client.get('/api/uploads/presign?ext=wav',
                     headers=auth_headers).json()['object_key']
    headers = dict(auth_headers, **{'content-length': '11'})
    r = client.put(f'/api/uploads/{key}', headers=headers, data=b'x' * 11)
    assert r.status_code == 413


def test_put_upload_oversized_body_is_413(client, auth_headers, monkeypatch):
    monkeypatch.setattr('fastapi_app.routers.uploads.MAX_UPLOAD_BYTES', 10)
    key = client.get('/api/uploads/presign?ext=wav',
                     headers=auth_headers).json()['object_key']
    r = client.put(f'/api/uploads/{key}', headers=auth_headers,
                   content=iter([b'x' * 11]))
    assert r.status_code == 413
