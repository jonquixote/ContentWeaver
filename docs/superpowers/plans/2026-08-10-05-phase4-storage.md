# Phase 4: Storage (R2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move generated videos, thumbnails, and voice reference clips from local disk to **Cloudflare R2** (S3-compatible, $0 egress), using **MinIO** for local dev. Presigned URLs for upload/download. Full abstraction so storage backend is swappable.

**Architecture:** New `src/services/storage/` package with a `StorageProvider` interface + `S3StorageProvider` (boto3 → R2/MinIO) and `LocalStorageProvider` (dev fallback). Celery tasks write final output to storage; `video_url`/`thumbnail_url` in task/project responses become presigned URLs. Voice reference uploads go through presigned PUT. Config via env.

**Tech Stack:** boto3 (new dep), MinIO (docker-compose already has it), Cloudflare R2. No app-visible API changes — response shape stays `{video_url}`.

## Global Constraints

- Presigned URLs expire (default 1h); frontend refreshes via `GET /api/tasks/<id>/status` which regenerates URL
- Private bucket: objects never public-read; access only via presigned URL
- Upload paths: `videos/<user_id>/<project_id>/<task_id>.mp4`, `thumbs/<user_id>/<project_id>/<task_id>.jpg`, `voices/<user_id>/<voice_id>.wav`
- Local dev uses MinIO at `localhost:9000`; `STORAGE_BACKEND=minio|local`
- Existing local files: migration script uploads `final/` + `work/` to R2 once
- Content-Type set on upload (important for browser playback + download)
- Never commit R2/MinIO credentials

---

### Task 1: Storage abstraction package

**Files:**
- Create: `src/services/storage/__init__.py`
- Create: `src/services/storage/base.py`
- Create: `src/services/storage/s3_provider.py`
- Create: `src/services/storage/local_provider.py`
- Modify: `requirements.txt` (boto3)

**Interfaces:**
- Produces: `StorageProvider` with `put_object`, `get_presigned_url`, `delete_object`, `object_exists`

- [ ] **Step 1: Add boto3 to requirements**

```
boto3==1.38.13
```

Install: `pip install boto3==1.38.13`

- [ ] **Step 2: base.py**

```python
from abc import ABC, abstractmethod

class StorageProvider(ABC):
    @abstractmethod
    def put_object(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get_presigned_url(self, key: str, expires=3600) -> str | None: ...

    @abstractmethod
    def delete_object(self, key: str) -> None: ...

    @abstractmethod
    def object_exists(self, key: str) -> bool: ...
```

- [ ] **Step 3: s3_provider.py (boto3 → R2/MinIO)**

```python
import os, boto3
from botocore.config import Config
from .base import StorageProvider

class S3StorageProvider(StorageProvider):
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
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

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
```

- [ ] **Step 4: local_provider.py**

Mirror S3 provider but store under `uploads/` dir, return `/media/<key>` static URL, delete from disk.

- [ ] **Step 5: `__init__.py` factory**

```python
import os
from .s3_provider import S3StorageProvider
from .local_provider import LocalStorageProvider

_STORAGE = None

def get_storage():
    global _STORAGE
    if _STORAGE is None:
        backend = os.getenv('STORAGE_BACKEND', 'local')
        _STORAGE = S3StorageProvider() if backend in ('s3', 'minio', 'r2') else LocalStorageProvider()
    return _STORAGE
```

- [ ] **Step 6: Verify**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv312/bin/activate
python - <<'EOF'
from src.services.storage import get_storage
s = get_storage()  # local by default
s.put_object('test/hello.txt', b'hi', 'text/plain')
assert s.object_exists('test/hello.txt')
print(s.get_presigned_url('test/hello.txt'))
s.delete_object('test/hello.txt')
print('storage OK')
EOF
```

- [ ] **Step 7: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: pluggable storage provider (local/S3/R2/MinIO)"
```

---

### Task 2: MinIO dev environment

**Files:**
- Modify: `money_weaver_backend/docker-compose.yml` (ensure MinIO service + bucket init)

**Interfaces:**
- Produces: `docker compose up minio` gives S3 at `localhost:9000`

- [ ] **Step 1: Verify docker-compose has MinIO**

Existing file already has `minio` service (minioadmin/minioadmin-change-me). Add a `minio-init` service or entrypoint that creates bucket `moneyweaver`:

```yaml
  minio-init:
    image: minio/mc
    depends_on: [minio]
    entrypoint: >
      /bin/sh -c "
      mc alias set local http://minio:9000 minioadmin minioadmin-change-me;
      mc mb -p local/moneyweaver;
      "
```

- [ ] **Step 2: Start and test**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
docker compose up -d minio minio-init
STORAGE_BACKEND=s3 STORAGE_ENDPOINT=http://localhost:9000 \
STORAGE_ACCESS_KEY=minioadmin STORAGE_SECRET_KEY=minioadmin-change-me STORAGE_BUCKET=moneyweaver \
python - <<'EOF'
from src.services.storage import get_storage
s = get_storage()
s.put_object('test/hi.txt', b'hello', 'text/plain')
print(s.get_presigned_url('test/hi.txt'))
EOF
```

Expected: presigned URL prints; open in browser shows `hello`.

- [ ] **Step 3: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: minio bucket init for dev storage"
```

---

### Task 3: Store generated videos + thumbnails in storage

**Files:**
- Modify: `src/tasks/video_tasks.py`
- Modify: `src/routes/task.py` (presigned URL in status)
- Modify: `src/routes/project.py` (presigned video URL)

**Interfaces:**
- Produces: after assembly, task uploads `final/<project_id>/<task_id>.mp4` + thumbnail to storage; status returns presigned URLs

- [ ] **Step 1: Upload in assembler task**

After ffmpeg produces final mp4:

```python
from src.services.storage import get_storage
storage = get_storage()
with open(video_path, 'rb') as f:
    storage.put_object(f'videos/{task.user_id}/{task.project_id}/{task.id}.mp4', f.read(), 'video/mp4')
with open(thumb_path, 'rb') as f:
    storage.put_object(f'thumbs/{task.user_id}/{task.project_id}/{task.id}.jpg', f.read(), 'image/jpeg')
```

Keep local file during dev; production may delete after upload.

- [ ] **Step 2: Status endpoint returns presigned URLs**

```python
storage = get_storage()
key = f'videos/{task.user_id}/{task.project_id}/{task.id}.mp4'
task_dict['video_url'] = storage.get_presigned_url(key) if task.status == 'completed' else None
task_dict['thumbnail_url'] = storage.get_presigned_url(f'thumbs/{task.user_id}/{task.project_id}/{task.id}.jpg') if task.status == 'completed' else None
```

- [ ] **Step 3: Verify**

```bash
docker compose up -d minio
STORAGE_BACKEND=s3 STORAGE_ENDPOINT=http://localhost:9000 \
STORAGE_ACCESS_KEY=minioadmin STORAGE_SECRET_KEY=minioadmin-change-me \
python src/main.py &
# generate a short video via API, check status returns video_url
```

- [ ] **Step 4: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: upload generated videos and thumbs to storage, presigned URLs"
```

---

### Task 4: Voice reference upload via presigned PUT

**Files:**
- Modify: `src/routes/voices.py`
- Modify: `src/routes/upload.py` (new presigned upload endpoint)
- Modify: `src/services/api.js` (frontend upload via presigned URL)

**Interfaces:**
- Produces: `GET /api/uploads/presign?path=voices/<user>/<name>` returns `{upload_url, public_url}`; frontend PUTs directly to R2/MinIO

- [ ] **Step 1: Presign endpoint**

```python
@upload_bp.route('/api/uploads/presign', methods=['GET'])
@auth_required
def presign_upload():
    path = request.args.get('path')  # e.g. voices/12/ref-a.wav
    # validate: no '..', whitelisted prefixes
    storage = get_storage()
    url = storage.get_presigned_upload_url(path, expires=600)  # add method to base
    return jsonify({'upload_url': url, 'object_key': path})
```

Add `get_presigned_upload_url` to base + both providers (`generate_presigned_url('put_object', ...)` for S3, local returns a dev URL).

- [ ] **Step 2: Update create_voice flow**

Frontend: `presign` → `PUT` audio bytes to `upload_url` → then `POST /api/voices` with `{name, reference_audio_url: public base + key}`. Backend stores `reference_audio_url` as the key.

- [ ] **Step 3: Update api.js**

```js
presignUpload: (path) => api.get(`/uploads/presign?path=${encodeURIComponent(path)}`),
```

- [ ] **Step 4: Verify + commit**

Upload a voice clip → confirm object in MinIO bucket + preview plays.

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: presigned uploads for voice reference audio"
```

---

### Task 5: Migration script for existing local files

**Files:**
- Create: `money_weaver_backend/scripts/migrate_to_r2.py`

**Interfaces:**
- Produces: one-shot upload of `final/`, `work/`, `uploads/` to R2 with matching keys; idempotent (skip existing)

- [ ] **Step 1: Script**

```python
# scripts/migrate_to_r2.py
import os, glob
from src.services.storage import get_storage

ROOT = os.getenv('MIGRATE_ROOT', '.')
def main():
    storage = get_storage()
    for pattern in ('final/**/*.mp4', 'work/**/*.mp4', 'uploads/**/*'):
        for path in glob.glob(os.path.join(ROOT, pattern), recursive=True):
            key = path.replace(ROOT + '/', '').replace('\\', '/')
            if storage.object_exists(key):
                continue
            with open(path, 'rb') as f:
                storage.put_object(key, f.read(), guess_type(path))
            print(f'uploaded {key}')
```

Run: `python scripts/migrate_to_r2.py`

- [ ] **Step 2: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: local-to-R2 migration script"
```

---

### Task 6: Phase 4 verification

- [ ] **Step 1: Dev run with MinIO**

Whole app running with `STORAGE_BACKEND=s3` against MinIO: create video, check `video_url` plays in browser.

- [ ] **Step 2: R2 smoke (if credentials available)**

Set `STORAGE_ENDPOINT` to R2 URL + keys in `.env`; upload one object; fetch presigned URL; download 200.

- [ ] **Step 3: Fallback to local still works**

With no storage env, app uses `local` provider and returns local URLs.

- [ ] **Step 4: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: phase 4 storage verified"
```
