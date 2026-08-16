from flask import Blueprint, jsonify, request
from src.models.user import User
from src.database import db
from src.auth import auth_required, current_token_blocklist_entry
from src.validation import require_fields
from sqlalchemy.exc import IntegrityError

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/auth/register', methods=['POST'])
def register():
    data = request.json
    
    # Validate required fields
    try:
        require_fields(data, ['email', 'password', 'username'])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    if not isinstance(data.get('password'), str):
        return jsonify({'error': 'Password must be a string'}), 400
    
    # Check if user already exists
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'User with this email already exists'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'User with this username already exists'}), 400
    
    # Create new user
    user = User(
        username=data['username'],
        email=data['email']
    )
    user.hash_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    # Generate token
    token = user.generate_token()
    
    return jsonify({
        'user': user.to_dict(),
        'token': token
    }), 201

@auth_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.json
    
    # Validate required fields
    try:
        require_fields(data, ['email', 'password'])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    if not isinstance(data.get('password'), str):
        return jsonify({'error': 'Password must be a string'}), 400
    
    # Find user
    user = User.query.filter_by(email=data['email']).first()
    if not user or not user.verify_password(data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401
    
    db.session.commit()
    
    # Generate token
    token = user.generate_token()
    
    return jsonify({
        'user': user.to_dict(),
        'token': token
    })

@auth_bp.route('/auth/logout', methods=['POST'])
@auth_required
def logout():
    block = current_token_blocklist_entry()
    if block is not None:
        db.session.add(block)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    return jsonify({'message': 'Logged out'}), 200

@auth_bp.route('/auth/me', methods=['GET'])
@auth_required
def get_current_user():
    from flask import g
    user = User.query.get_or_404(g.current_user['id'])
    return jsonify(user.to_dict())