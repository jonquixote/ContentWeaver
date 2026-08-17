from flask import Blueprint, jsonify, request, g
from src.models.user import User
from src.database import db
from src.auth import auth_required, current_token_blocklist_entry
from src.validation import require_fields
from sqlalchemy.exc import IntegrityError

user_bp = Blueprint('user', __name__)


def _apply_user_update(user, data):
    """Apply partial user updates (username/email/password).

    Returns an error tuple (jsonify response, status code) on failure, or None
    after a successful commit. Shared by PUT /users/<id> and PATCH /users/me.
    """
    try:
        require_fields(data, [])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    if 'username' in data and not str(data['username']).strip():
        return jsonify({'error': 'Username cannot be empty'}), 400
    if 'email' in data and not str(data['email']).strip():
        return jsonify({'error': 'Email cannot be empty'}), 400
    user.username = data.get('username', user.username)
    user.email = data.get('email', user.email)
    if 'password' in data:
        if not isinstance(data['password'], str):
            return jsonify({'error': 'Password must be a string'}), 400
        user.hash_password(data['password'])
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Username or email already in use'}), 409
    return None


@user_bp.route('/users/me', methods=['GET'])
@auth_required
def get_me():
    user = User.query.get_or_404(g.current_user['id'])
    return jsonify(user.to_dict())


@user_bp.route('/users/me', methods=['PATCH'])
@auth_required
def update_me():
    user = User.query.get_or_404(g.current_user['id'])
    data = request.json
    error = _apply_user_update(user, data)
    if error:
        return error
    return jsonify(user.to_dict())


def _user_has_child_data(user_id):
    """True when the user owns rows that FK-reference user.id (Project, ApiKey).

    SQLite (this app's dev/prod DB) does not enforce foreign keys by default, so
    deleting such a user would silently orphan rows instead of raising an
    IntegrityError. Check explicitly so the 409 path behaves identically on
    SQLite and PostgreSQL.
    """
    from src.models.project import Project
    from src.models.api_key import ApiKey
    return (Project.query.filter_by(user_id=user_id).first() is not None
            or ApiKey.query.filter_by(user_id=user_id).first() is not None)


_CHILD_DATA_ERROR = ('Delete projects and API keys first, or contact support', 409)


@user_bp.route('/users/me', methods=['DELETE'])
@auth_required
def delete_me():
    user = User.query.get_or_404(g.current_user['id'])
    if _user_has_child_data(user.id):
        return jsonify({'error': _CHILD_DATA_ERROR[0]}), _CHILD_DATA_ERROR[1]
    block = current_token_blocklist_entry()
    if block is not None:
        db.session.add(block)
    try:
        db.session.delete(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': _CHILD_DATA_ERROR[0]}), _CHILD_DATA_ERROR[1]
    return '', 204

@user_bp.route('/users', methods=['GET'])
@auth_required
def get_users():
    user = User.query.get_or_404(g.current_user['id'])
    return jsonify([user.to_dict()])

@user_bp.route('/users', methods=['POST'])
@auth_required
def create_user():
    data = request.json
    try:
        require_fields(data, ['username', 'email', 'password'])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    if not isinstance(data.get('password'), str):
        return jsonify({'error': 'Password must be a string'}), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'User with this username already exists'}), 409
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'User with this email already exists'}), 409
    user = User(username=data['username'], email=data['email'])
    user.hash_password(data['password'])
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Username or email already in use'}), 409
    return jsonify(user.to_dict()), 201

@user_bp.route('/users/<int:user_id>', methods=['GET'])
@auth_required
def get_user(user_id):
    if user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@user_bp.route('/users/<int:user_id>', methods=['PUT'])
@auth_required
def update_user(user_id):
    if user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    user = User.query.get_or_404(user_id)
    data = request.json
    error = _apply_user_update(user, data)
    if error:
        return error
    return jsonify(user.to_dict())

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
@auth_required
def delete_user(user_id):
    if user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    user = User.query.get_or_404(user_id)
    if _user_has_child_data(user.id):
        return jsonify({'error': _CHILD_DATA_ERROR[0]}), _CHILD_DATA_ERROR[1]
    try:
        db.session.delete(user)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': _CHILD_DATA_ERROR[0]}), _CHILD_DATA_ERROR[1]
    return '', 204
