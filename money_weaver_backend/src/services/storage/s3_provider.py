import logging
import os

import boto3
from botocore.config import Config

from .base import StorageProvider

logger = logging.getLogger(__name__)


class S3StorageProvider(StorageProvider):
    """S3-compatible object storage backend (AWS S3, Cloudflare R2, MinIO)."""

    def __init__(self):
        self.bucket = os.getenv('STORAGE_BUCKET', 'moneyweaver')
        endpoint = os.getenv('STORAGE_ENDPOINT')  # https://<acct>.r2.cloudflarestorage.com OR http://localhost:9000
        self.client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=os.getenv('STORAGE_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('STORAGE_SECRET_KEY'),
            region_name=os.getenv('STORAGE_REGION', 'auto'),
            config=Config(signature_version='s3v4'),
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return
        except Exception:
            pass
        # Bucket creation may be forbidden (e.g. R2 requires manual creation);
        # warn instead of failing so __init__ never crashes on a permission error.
        try:
            self.client.create_bucket(Bucket=self.bucket)
        except Exception as e:
            logger.warning('Could not create storage bucket %r: %s', self.bucket, e)

    def put_object(self, key, data, content_type):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get_presigned_url(self, key, expires=3600):
        return self.client.generate_presigned_url('get_object', Params={'Bucket': self.bucket, 'Key': key}, ExpiresIn=expires)

    def delete_object(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def object_exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False