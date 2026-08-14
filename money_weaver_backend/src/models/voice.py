from datetime import datetime

# Import db inside functions to avoid circular imports
def get_db():
    from src.database import db
    return db


class Voice(get_db().Model):
    __tablename__ = 'voices'

    id = get_db().Column(get_db().Integer, primary_key=True)
    user_id = get_db().Column(get_db().Integer, nullable=False, index=True)
    name = get_db().Column(get_db().String(100), nullable=False)
    reference_audio_url = get_db().Column(get_db().String(500), nullable=False)  # storage key (e.g. voices/<user_id>/<uuid>.<ext>) resolved by the routes layer, or legacy local path
    description = get_db().Column(get_db().String(300), default='')
    created_at = get_db().Column(get_db().DateTime, default=datetime.utcnow)
    consent_confirmed_at = get_db().Column(get_db().DateTime, nullable=True)
    last_used_at = get_db().Column(get_db().DateTime, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'reference_audio_url': self.reference_audio_url,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'consent_confirmed_at': self.consent_confirmed_at.isoformat() if self.consent_confirmed_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None
        }

    def __repr__(self):
        return f'<Voice {self.name} (user {self.user_id})>'