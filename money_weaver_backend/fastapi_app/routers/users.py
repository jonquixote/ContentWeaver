import os
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from fastapi_app.db import get_db
from fastapi_app.deps import bearer, current_user
from src.models.token_blocklist import TokenBlocklist
from src.models.user import User
from src.validation import require_fields

router = APIRouter(prefix='/api/users', tags=['users'])


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


class UserCreate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None


def _apply_user_update(user, data, session):
    """Apply partial user updates (username/email/password).

    Returns an error tuple (message, status) on failure, or None after a
    successful commit. Shared by PUT /users/{id} and PATCH /users/me.
    """
    try:
        require_fields(data, [])
    except ValueError as e:
        return str(e), 400
    if 'username' in data and (data['username'] is None or not str(data['username']).strip()):
        return 'Username cannot be empty', 400
    if 'email' in data and (data['email'] is None or not str(data['email']).strip()):
        return 'Email cannot be empty', 400
    user.username = data.get('username', user.username)
    user.email = data.get('email', user.email)
    if 'password' in data:
        if not isinstance(data['password'], str):
            return 'Password must be a string', 400
        user.hash_password(data['password'])
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return 'Username or email already in use', 409
    return None


@router.get('/me')
def get_me(user=Depends(current_user)):
    return user.to_dict()


@router.patch('/me')
def update_me(body: UserUpdate, user=Depends(current_user), session=Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    error = _apply_user_update(user, data, session)
    if error:
        raise HTTPException(error[1], error[0])
    return user.to_dict()


def _user_has_child_data(session, user_id):
    """True when the user owns rows that FK-reference user.id (Project, ApiKey).

    SQLite (this app's dev/prod DB) does not enforce foreign keys by default, so
    deleting such a user would silently orphan rows instead of raising an
    IntegrityError. Check explicitly so the 409 path behaves identically on
    SQLite and PostgreSQL.
    """
    from src.models.project import Project
    from src.models.api_key import ApiKey
    return (session.query(Project).filter_by(user_id=user_id).first() is not None
            or session.query(ApiKey).filter_by(user_id=user_id).first() is not None)


_CHILD_DATA_ERROR = ('Delete projects and API keys first, or contact support', 409)


@router.delete('/me')
def delete_me(creds: HTTPAuthorizationCredentials = Depends(bearer),
              user=Depends(current_user),
              session=Depends(get_db)):
    if _user_has_child_data(session, user.id):
        raise HTTPException(_CHILD_DATA_ERROR[1], _CHILD_DATA_ERROR[0])
    payload = jwt.decode(creds.credentials, os.environ['SECRET_KEY'], algorithms=['HS256'])
    block = TokenBlocklist(jti=payload.get('jti'))
    if block.jti:
        session.add(block)
    try:
        session.delete(user)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(_CHILD_DATA_ERROR[1], _CHILD_DATA_ERROR[0])
    return Response(status_code=204)


@router.get('')
def get_users(user=Depends(current_user)):
    return [user.to_dict()]


@router.post('', status_code=201)
def create_user(body: UserCreate, user=Depends(current_user), session=Depends(get_db)):
    data = body.model_dump()
    try:
        require_fields(data, ['username', 'email', 'password'])
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not isinstance(data.get('password'), str):
        raise HTTPException(400, 'Password must be a string')
    if session.query(User).filter_by(username=data['username']).first():
        raise HTTPException(409, 'User with this username already exists')
    if session.query(User).filter_by(email=data['email']).first():
        raise HTTPException(409, 'User with this email already exists')
    new_user = User(username=data['username'], email=data['email'])
    new_user.hash_password(data['password'])
    session.add(new_user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, 'Username or email already in use')
    return new_user.to_dict()


@router.get('/{user_id}')
def get_user(user_id: int, user=Depends(current_user), session=Depends(get_db)):
    if user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(404, 'Not found')
    return target.to_dict()


@router.put('/{user_id}')
def update_user(user_id: int, body: UserUpdate, user=Depends(current_user), session=Depends(get_db)):
    if user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(404, 'Not found')
    data = body.model_dump(exclude_unset=True)
    error = _apply_user_update(target, data, session)
    if error:
        raise HTTPException(error[1], error[0])
    return target.to_dict()


@router.delete('/{user_id}')
def delete_user(user_id: int, user=Depends(current_user), session=Depends(get_db)):
    if user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(404, 'Not found')
    if _user_has_child_data(session, target.id):
        raise HTTPException(_CHILD_DATA_ERROR[1], _CHILD_DATA_ERROR[0])
    try:
        session.delete(target)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(_CHILD_DATA_ERROR[1], _CHILD_DATA_ERROR[0])
    return Response(status_code=204)