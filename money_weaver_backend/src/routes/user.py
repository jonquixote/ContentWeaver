from flask import Blueprint, jsonify, request, g
from src.models.user import User
from src.database import db
from src.auth import auth_required

user_bp = Blueprint('user', __name__)

@user_bp.route('/users', methods=['GET'])
@auth_required
def get_users():
    user = User.query.get_or_404(g.current_user['id'])
    return jsonify([user.to_dict()])

@user_bp.route('/users', methods=['POST'])
@auth_required
def create_user():
    data = request.json
    if not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'username, email, and password are required'}), 400
    user = User(username=data['username'], email=data['email'])
    user.hash_password(data['password'])
    db.session.add(user)
    db.session.commit()
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
    user.username = data.get('username', user.username)
    user.email = data.get('email', user.email)
    if 'password' in data:
        user.hash_password(data['password'])
    db.session.commit()
    return jsonify(user.to_dict())

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
@auth_required
def delete_user(user_id):
    if user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return '', 204
