"""Storage-provider abstraction tests.

Covers the local-disk backend with a real round-trip through STORAGE_LOCAL_DIR
and the S3/R2/MinIO backend with boto3 fully stubbed (no network). Each test
switches STORAGE_BACKEND, so both reset the module-level get_storage() singleton
after changing env and restore it afterwards to avoid leaking a provider into
later tests.
"""
import io

import src.services.storage as st
from src.services.storage.local_provider import LocalStorageProvider
from src.services.storage.s3_provider import S3StorageProvider


def _reset_storage():
    st._STORAGE = None


def test_local_provider_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'local')
    monkeypatch.setenv('STORAGE_LOCAL_DIR', str(tmp_path))
    # STORAGE_LOCAL_DIR is read into local_provider.STORAGE_LOCAL_DIR at import
    # time, so patch the module constant as well as the env var.
    import src.services.storage.local_provider as lp
    monkeypatch.setattr(lp, 'STORAGE_LOCAL_DIR', str(tmp_path))
    _reset_storage()
    try:
        storage = st.get_storage()
        assert isinstance(storage, LocalStorageProvider)

        storage.put_object('k.txt', b'data', 'text/plain')
        assert storage.object_exists('k.txt')
        assert storage.get_object('k.txt') == b'data'
        assert storage.get_presigned_url('k.txt') == '/media/k.txt'
        assert storage.get_presigned_upload_url('k.txt')
        storage.delete_object('k.txt')
        assert not storage.object_exists('k.txt')
    finally:
        _reset_storage()


class _S3Stub:
    """In-memory boto3 's3' client stub. Records calls, returns canned responses."""

    def __init__(self):
        self.calls = []
        self.head_object_failures = set()

    def _record(self, method, **kwargs):
        self.calls.append((method, kwargs))

    def head_bucket(self, **kwargs):
        self._record('head_bucket', **kwargs)

    def create_bucket(self, **kwargs):
        self._record('create_bucket', **kwargs)

    def put_object(self, **kwargs):
        self._record('put_object', **kwargs)

    def get_object(self, **kwargs):
        self._record('get_object', **kwargs)
        return {'Body': io.BytesIO(b'data')}

    def generate_presigned_url(self, client_method, **kwargs):
        self._record('generate_presigned_url', client_method=client_method, kwargs=kwargs)
        return f'https://presigned.example/{kwargs["Params"]["Key"]}'

    def delete_object(self, **kwargs):
        self._record('delete_object', **kwargs)

    def head_object(self, **kwargs):
        self._record('head_object', **kwargs)
        if kwargs['Key'] in self.head_object_failures:
            raise Exception('not found')
        return {'ETag': 'stub'}


def test_s3_provider_calls_through_to_boto3(monkeypatch):
    stub = _S3Stub()
    monkeypatch.setenv('STORAGE_BACKEND', 's3')
    monkeypatch.setenv('STORAGE_BUCKET', 'mw-test-bucket')
    monkeypatch.setattr('src.services.storage.s3_provider.boto3.client',
                        lambda *a, **k: stub)
    _reset_storage()
    try:
        storage = st.get_storage()
        assert isinstance(storage, S3StorageProvider)

        storage.put_object('a/b.txt', b'data', 'text/plain')
        assert storage.object_exists('a/b.txt')
        assert storage.get_object('a/b.txt') == b'data'
        assert storage.get_presigned_url('a/b.txt') == 'https://presigned.example/a/b.txt'
        stub.head_object_failures.add('a/b.txt')
        assert not storage.object_exists('a/b.txt')
        storage.delete_object('a/b.txt')

        calls_by_method = {}
        for method, kwargs in stub.calls:
            calls_by_method.setdefault(method, []).append(kwargs)

        assert calls_by_method['head_bucket'] == [{'Bucket': 'mw-test-bucket'}]
        assert calls_by_method['put_object'] == [{
            'Bucket': 'mw-test-bucket', 'Key': 'a/b.txt',
            'Body': b'data', 'ContentType': 'text/plain'}]
        assert all(c['Bucket'] == 'mw-test-bucket' for c in calls_by_method['head_object'])
        assert calls_by_method['head_object'][0]['Key'] == 'a/b.txt'
        assert calls_by_method['get_object'] == [{'Bucket': 'mw-test-bucket', 'Key': 'a/b.txt'}]
        assert calls_by_method['delete_object'] == [{'Bucket': 'mw-test-bucket', 'Key': 'a/b.txt'}]
        presign = calls_by_method['generate_presigned_url']
        assert presign[0]['client_method'] == 'get_object'
        assert presign[0]['kwargs'] == {
            'Params': {'Bucket': 'mw-test-bucket', 'Key': 'a/b.txt'}, 'ExpiresIn': 3600}
    finally:
        _reset_storage()
