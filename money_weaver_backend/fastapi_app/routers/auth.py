import os

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.exc import IntegrityError

from fastapi_app.db import get_db
from fastapi_app.deps import bearer, current_user
from fastapi_app.schemas.auth import LoginRequest, RegisterRequest
from src.models.token_blocklist import TokenBlocklist
from src.models.user import User

router = APIRouter(prefix='/api/auth', tags=['auth'])


@router.post('/register', status_code=201)
def register(body: RegisterRequest, session=Depends(get_db)):
    if session.query(User).filter_by(email=body.email).first():
        raise HTTPException(400, 'User with this email already exists')
    if session.query(User).filter_by(username=body.username).first():
        raise HTTPException(400, 'User with this username already exists')

    user = User(username=body.username, email=body.email)
    user.hash_password(body.password)
    session.add(user)
    session.commit()

    token = user.generate_token()
    return {'user': user.to_dict(), 'token': token}


@router.post('/login')
def login(body: LoginRequest, session=Depends(get_db)):
    user = session.query(User).filter_by(email=body.email).first()
    if not user or not user.verify_password(body.password):
        raise HTTPException(401, 'Invalid email or password')

    session.commit()

    token = user.generate_token()
    return {'user': user.to_dict(), 'token': token}


@router.post('/logout')
def logout(creds: HTTPAuthorizationCredentials = Depends(bearer),
           _user=Depends(current_user),
           session=Depends(get_db)):
    try:
        payload = jwt.decode(creds.credentials, os.environ['SECRET_KEY'], algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, 'Token expired')
    except jwt.InvalidTokenError:
        raise HTTPException(401, 'Invalid token')
    block = TokenBlocklist(jti=payload.get('jti'))
    if block.jti:
        session.add(block)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
    return {'message': 'Logged out'}


@router.get('/me')
def me(user=Depends(current_user)):
    return user.to_dict()