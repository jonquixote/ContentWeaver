from datetime import datetime

# Import db inside functions to avoid circular imports
def get_db():
    from src.database import db
    return db

class VideoTemplate(get_db().Model):
    __tablename__ = 'video_templates'

    id = get_db().Column(get_db().Integer, primary_key=True)
    user_id = get_db().Column(get_db().Integer, nullable=False)
    name = get_db().Column(get_db().String(100), nullable=False)
    description = get_db().Column(get_db().Text, default='')
    config = get_db().Column(get_db().JSON, nullable=False)   # preset id, voice, duration, caption style
    is_public = get_db().Column(get_db().Boolean, default=False)
    created_at = get_db().Column(get_db().DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'config': self.config,
            'is_public': self.is_public,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<VideoTemplate {self.name}>'
