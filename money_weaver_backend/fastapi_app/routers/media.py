import os

import jwt
from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, PlainTextResponse

from fastapi_app.db import db_session
from src.models.token_blocklist import TokenBlocklist

router = APIRouter(tags=['media'])

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FINAL_DIR = os.path.join(_BACKEND_DIR, 'final')
MEDIA_DIR = os.environ.get('STORAGE_LOCAL_DIR', os.path.join(_BACKEND_DIR, 'uploads'))


def _token_from_request(request: Request):
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return request.query_params.get('token')


def _auth_error(token):
    if not token:
        return 'Authentication required'
    try:
        payload = jwt.decode(token, os.environ['SECRET_KEY'], algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return 'Token expired'
    except jwt.InvalidTokenError:
        return 'Invalid token'
    with db_session() as session:
        if payload.get('jti') and session.query(TokenBlocklist).filter_by(jti=payload['jti']).first():
            return 'Token revoked'
    return None


def _serve(base_dir, filename, not_found_msg, request):
    token = _token_from_request(request)
    err = _auth_error(token)
    if err:
        return PlainTextResponse(err, 401)
    full = os.path.abspath(os.path.join(base_dir, filename))
    if not full.startswith(os.path.abspath(base_dir)):
        return PlainTextResponse(not_found_msg, 404)
    if os.path.isfile(full):
        return FileResponse(full)
    return PlainTextResponse(not_found_msg, 404)


@router.get('/final/{filename:path}', include_in_schema=False)
def serve_final(filename: str, request: Request):
    return _serve(FINAL_DIR, filename, 'Video not found', request)


@router.get('/media/{filename:path}', include_in_schema=False)
def serve_media(filename: str, request: Request):
    return _serve(MEDIA_DIR, filename, 'Media not found', request)