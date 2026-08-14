#!/usr/bin/env python3
"""One-shot archival migration of existing local media files to object storage.

Run from money_weaver_backend:
    ./venv/bin/python scripts/migrate_to_r2.py

What it does:
    Walks final/**/*.mp4, work/**/* and uploads/**/* under MIGRATE_ROOT
    (default: the money_weaver_backend directory) and uploads each file to the
    configured storage backend under a key equal to its path relative to
    MIGRATE_ROOT (e.g. final/foo.mp4, work/bar.wav, uploads/<uid>/voices/x.wav).
    Idempotent: any key that already exists is skipped, so re-running only
    uploads what's missing. Prints each uploaded key and a final count; exits
    non-zero on a hard failure.

Environment:
    MIGRATE_ROOT          Root directory to migrate (default: money_weaver_backend)
    STORAGE_BACKEND       local (default) | s3 | minio | r2

    For local verification (no cloud credentials needed):
    STORAGE_LOCAL_DIR     Where local-provider objects land (default: uploads/)

    For S3 / R2 / MinIO:
    STORAGE_ENDPOINT      e.g. https://<acct>.r2.cloudflarestorage.com or http://localhost:9000
    STORAGE_ACCESS_KEY    Access key id (set it in your environment; do NOT commit)
    STORAGE_SECRET_KEY    Secret access key (set it in your environment; do NOT commit)
    STORAGE_BUCKET        Bucket name (default: moneyweaver)

NOTE: never hardcode or commit R2/MinIO credentials. Keep them in the
environment or a secret store.
"""

import glob
import mimetypes
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from src.services.storage import get_storage

DEFAULT_ROOT = BACKEND_DIR
PATTERNS = ('final/**/*.mp4', 'work/**/*', 'uploads/**/*')


def main():
    root = os.path.abspath(os.getenv('MIGRATE_ROOT', DEFAULT_ROOT))
    if not os.path.isdir(root):
        print(f'migrate_to_r2: MIGRATE_ROOT not a directory: {root}', file=sys.stderr)
        return 1

    storage = get_storage()
    uploaded = 0
    failed = False

    for pattern in PATTERNS:
        for path in glob.glob(os.path.join(root, pattern), recursive=True):
            if not os.path.isfile(path):
                continue
            name = os.path.basename(path)
            if name.startswith('._') or name == '.DS_Store':
                continue
            key = path.replace(root + os.sep, '').replace('\\', '/')
            if storage.object_exists(key):
                continue
            content_type = mimetypes.guess_type(key)[0] or 'application/octet-stream'
            try:
                with open(path, 'rb') as f:
                    storage.put_object(key, f.read(), content_type)
            except Exception as e:
                print(f'failed {key}: {e}', file=sys.stderr)
                failed = True
                continue
            uploaded += 1
            print(f'uploaded {key}')

    print(f'done: {uploaded} file(s) uploaded')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
