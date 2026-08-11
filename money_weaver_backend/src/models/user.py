from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import jwt
import os

# Import db inside functions to avoid circular imports
def get_db():
    from src.database import db
    return db

class User(get_db().Model):
    __tablename__ = 'user'
    
    id = get_db().Column(get_db().Integer, primary_key=True)
    username = get_db().Column(get_db().String(80), unique=True, nullable=False)
    email = get_db().Column(get_db().String(120), unique=True, nullable=False)
    password_hash = get_db().Column(get_db().String(120), nullable=False)
    created_at = get_db().Column(get_db().DateTime, default=datetime.utcnow)
    updated_at = get_db().Column(get_db().DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Simple relationship with projects (no back_populates to avoid circular imports)
    # projects = get_db().relationship('Project', back_populates='user')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def generate_token(self):
        payload = {
            'user_id': self.id,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        return jwt.encode(payload, os.environ['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_token(token):
        try:
            payload = jwt.decode(token, os.environ['SECRET_KEY'], algorithms=['HS256'])
            db = get_db()
            return db.session.get(User, payload['user_id'])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def __repr__(self):
        return f'<User {self.username}>'