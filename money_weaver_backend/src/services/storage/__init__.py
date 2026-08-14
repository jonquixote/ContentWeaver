import os

from .local_provider import LocalStorageProvider
from .s3_provider import S3StorageProvider

_STORAGE = None

VOICE_KEY_EXTENSIONS = ('wav', 'mp3')


def get_storage():
    global _STORAGE
    if _STORAGE is None:
        backend = os.getenv('STORAGE_BACKEND', 'local')
        _STORAGE = S3StorageProvider() if backend in ('s3', 'minio', 'r2') else LocalStorageProvider()
    return _STORAGE


def is_valid_storage_key(key, user_id):
    """Validate a voice-reference storage key: voices/<uid>/<name>.(wav|mp3)."""
    if not isinstance(key, str) or not key.startswith('voices/'):
        return False
    if '..' in key:
        return False
    parts = key.split('/')
    if len(parts) != 3 or parts[1] != str(user_id):
        return False
    name = parts[2]
    if not name or name.startswith('.') or '.' not in name:
        return False
    return name.rsplit('.', 1)[1].lower() in VOICE_KEY_EXTENSIONS


def resolve_reference_for_tts(reference):
    """Map a stored voice reference to a value the TTS microservice can consume.

    Storage keys (voices/...) resolve to a local filesystem path under the local
    provider (TTS reads it directly) or a presigned http(s) GET URL for
    S3/R2/MinIO. Legacy absolute filesystem paths pass through unchanged.
    """
    storage = get_storage()
    if isinstance(reference, str) and reference.startswith('voices/'):
        if isinstance(storage, LocalStorageProvider):
            return os.path.join(storage.root, reference)
        return storage.get_presigned_url(reference)
    return reference