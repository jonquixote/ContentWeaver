import os
from functools import wraps
from flask import request, jsonify, g
import jwt
from src.models.token_blocklist import TokenBlocklist

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
        g.current_user = {'id': payload['user_id'], 'username': payload.get('username', '')}
        return f(*args, **kwargs)
    return wrapper
