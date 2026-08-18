import os

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from fastapi_app.db import get_db
from src.models.token_blocklist import TokenBlocklist
from src.models.user import User

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer),
                 session=Depends(get_db)):
    if creds is None:
        raise HTTPException(401, 'Missing token')
    try:
        payload = jwt.decode(creds.credentials, os.environ['SECRET_KEY'], algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, 'Token expired')
    except Exception:
        raise HTTPException(401, 'Invalid token')
    if payload.get('jti') and session.query(TokenBlocklist).filter_by(jti=payload['jti']).first():
        raise HTTPException(401, 'Token revoked')
    user_id = payload.get('user_id')
    user = session.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(401, 'User no longer exists')
    return user