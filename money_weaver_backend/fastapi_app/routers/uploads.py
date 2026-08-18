import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from fastapi_app.deps import current_user
from src.services.storage import get_storage, is_valid_storage_key

router = APIRouter(prefix='/api/uploads', tags=['uploads'])

CONTENT_TYPES = {'wav': 'audio/wav', 'mp3': 'audio/mpeg'}
# Reference-audio cap enforced by validate_audio / the TTS service; reject at
# the proxy before buffering the whole body in RAM.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@router.get('/presign')
def presign_upload(ext: Optional[str] = None, user=Depends(current_user)):
    ext = (ext or '').lower().strip().lstrip('.')
    if ext not in CONTENT_TYPES:
        raise HTTPException(400, 'ext must be wav or mp3')

    # Mint the object key server-side; never trust a client-supplied path.
    key = f"voices/{user.id}/{uuid.uuid4().hex}.{ext}"
    try:
        upload_url = get_storage().get_presigned_upload_url(
            key, expires=600, content_type=CONTENT_TYPES[ext])
    except Exception as e:
        raise HTTPException(500, f'Failed to prepare upload: {e}')
    return {'upload_url': upload_url, 'object_key': key}


@router.put('/{key:path}')
async def put_upload(key: str, request: Request, user=Depends(current_user)):
    if not is_valid_storage_key(key, user.id):
        raise HTTPException(400, 'invalid upload path')

    content_length = request.headers.get('content-length')
    if content_length is not None:
        try:
            content_length = int(content_length)
        except (TypeError, ValueError):
            content_length = None
        if content_length is not None and content_length > MAX_UPLOAD_BYTES:
            raise HTTPException(413, 'upload body exceeds the 25MB cap')

    data = await request.body()
    if not data:
        raise HTTPException(400, 'empty upload body')
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, 'upload body exceeds the 25MB cap')

    ext = key.rsplit('.', 1)[1].lower()
    try:
        get_storage().put_object(key, data, CONTENT_TYPES[ext])
    except Exception as e:
        raise HTTPException(500, f'Upload failed: {e}')
    return {'ok': True, 'object_key': key}
