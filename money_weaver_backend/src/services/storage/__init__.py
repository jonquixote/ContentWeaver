import os

from .local_provider import LocalStorageProvider
from .s3_provider import S3StorageProvider

_STORAGE = None


def get_storage():
    global _STORAGE
    if _STORAGE is None:
        backend = os.getenv('STORAGE_BACKEND', 'local')
        _STORAGE = S3StorageProvider() if backend in ('s3', 'minio', 'r2') else LocalStorageProvider()
    return _STORAGE