from datetime import datetime


def get_db():
    from src.database import db
    return db


class ModelPreference(get_db().Model):
    __tablename__ = 'model_preference'

    id = get_db().Column(get_db().Integer, primary_key=True)
    user_id = get_db().Column(get_db().Integer, get_db().ForeignKey('user.id'), nullable=False, unique=True)
    defaults = get_db().Column(get_db().Text, nullable=True)    # JSON dict: {"script": "...", "idea": "..."}
    fallbacks = get_db().Column(get_db().Text, nullable=True)  # JSON list: ["modelA", "modelB"]
    created_at = get_db().Column(get_db().DateTime, default=datetime.utcnow)
    updated_at = get_db().Column(get_db().DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'user_id': self.user_id,
            'defaults': json.loads(self.defaults) if self.defaults else {},
            'fallbacks': json.loads(self.fallbacks) if self.fallbacks else [],
        }
