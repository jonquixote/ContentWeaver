import os
from functools import wraps
from flask import request, jsonify, g
import jwt
from src.models.token_blocklist import TokenBlocklist
from src.models.user import User


def current_token_blocklist_entry():
    """Return a TokenBlocklist for the current request's JWT jti, or None.

    Mirrors the /auth/logout revocation mechanism. Caller adds the entry to the
    session and commits, so it can be rolled back atomically with other changes.
    """
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    try:
        payload = jwt.decode(auth[7:], os.environ['SECRET_KEY'], algorithms=['HS256'])
    except jwt.InvalidTokenError:
        return None
    if payload.get('jti'):
        return TokenBlocklist(jti=payload['jti'])
    return None


def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid token'}), 401
        token = auth[7:]
        try:
            payload = jwt.decode(token, os.environ['SECRET_KEY'], algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        if payload.get('jti') and TokenBlocklist.query.filter_by(jti=payload['jti']).first():
            return jsonify({'error': 'Token revoked'}), 401
        user_id = payload.get('user_id')
        if user_id is None or User.query.get(user_id) is None:
            return jsonify({'error': 'User no longer exists'}), 401
        g.current_user = {'id': user_id, 'username': payload.get('username', '')}
        return f(*args, **kwargs)
    return wrapper
