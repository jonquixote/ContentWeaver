def get_db():
    from src.database import db
    return db

class FormatPreset(get_db().Model):
    __tablename__ = 'format_presets'

    id = get_db().Column(get_db().Integer, primary_key=True)
    name = get_db().Column(get_db().String(50), nullable=False, unique=True)
    platform = get_db().Column(get_db().String(50), nullable=False)
    width = get_db().Column(get_db().Integer, nullable=False)
    height = get_db().Column(get_db().Integer, nullable=False)
    fps = get_db().Column(get_db().Integer, nullable=False, default=30)
    duration_min = get_db().Column(get_db().Integer, nullable=False, default=15)
    duration_max = get_db().Column(get_db().Integer, nullable=False, default=120)
    is_default = get_db().Column(get_db().Boolean, default=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'platform': self.platform,
            'width': self.width,
            'height': self.height,
            'fps': self.fps,
            'duration_min': self.duration_min,
            'duration_max': self.duration_max,
            'is_default': self.is_default
        }

    def __repr__(self):
        return f'<FormatPreset {self.name}>'