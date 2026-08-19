import os

from .base import StorageProvider

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
STORAGE_LOCAL_DIR = os.environ.get('STORAGE_LOCAL_DIR', os.path.join(BASE_DIR, 'uploads'))


class LocalStorageProvider(StorageProvider):
    """Local-disk storage backend. Files land under STORAGE_LOCAL_DIR and are
    served by the /media/<key> route in fastapi_app/main.py."""

    def __init__(self):
        self.root = STORAGE_LOCAL_DIR
        os.makedirs(self.root, exist_ok=True)

    def _path(self, key):
        path = os.path.normpath(os.path.join(self.root, key))
        if path != self.root and not path.startswith(self.root + os.sep):
            raise ValueError(f'key escapes storage root: {key!r}')
        return path

    def put_object(self, key, data, content_type):
        path = self._path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)

    def get_object(self, key):
        with open(self._path(key), 'rb') as f:
            return f.read()

    def get_presigned_url(self, key, expires=3600):
        return f'/media/{key}'

    def get_presigned_upload_url(self, key, expires=600, content_type='application/octet-stream'):
        # Local storage is a GET-only static server (/media/<key>), so an upload
        # "presigned URL" is really the backend PUT-proxy route that streams the
        # body into put_object. The base host defaults to the dev backend; point
        # STORAGE_BACKEND_URL at the real API host in other environments.
        base = os.getenv('STORAGE_BACKEND_URL', 'http://localhost:5004')
        return f'{base.rstrip("/")}/api/uploads/{key}'

    def delete_object(self, key):
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)

    def object_exists(self, key):
        return os.path.exists(self._path(key))