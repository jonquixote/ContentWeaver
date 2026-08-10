from datetime import datetime

# Import db inside functions to avoid circular imports
def get_db():
    from src.database import db
    return db

class ApiKey(get_db().Model):
    __tablename__ = 'api_key'
    
    id = get_db().Column(get_db().Integer, primary_key=True)
    user_id = get_db().Column(get_db().Integer, get_db().ForeignKey('user.id'), nullable=False)
    name = get_db().Column(get_db().String(100), nullable=False)  # e.g., "OpenAI Production", "Anthropic Test"
    provider = get_db().Column(get_db().String(50), nullable=False)  # e.g., "openai", "anthropic", "google"
    key = get_db().Column(get_db().Text, nullable=False)  # Encrypted API key
    is_active = get_db().Column(get_db().Boolean, default=True)
    created_at = get_db().Column(get_db().DateTime, default=datetime.utcnow)
    updated_at = get_db().Column(get_db().DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Simple relationship with user (no backref to avoid circular imports)
    # user = get_db().relationship('User', backref=get_db().backref('api_keys', lazy=True))

    def __repr__(self):
        return f'<ApiKey {self.name} ({self.provider})>'

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'provider': self.provider,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }