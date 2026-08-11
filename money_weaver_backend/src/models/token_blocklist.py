from datetime import datetime

# Import db inside functions to avoid circular imports
def get_db():
    from src.database import db
    return db

class TokenBlocklist(get_db().Model):
    __tablename__ = 'token_blocklist'

    id = get_db().Column(get_db().Integer, primary_key=True)
    jti = get_db().Column(get_db().String(36), unique=True, nullable=False, index=True)
    created_at = get_db().Column(get_db().DateTime, default=datetime.utcnow)
