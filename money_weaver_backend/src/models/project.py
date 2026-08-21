from datetime import datetime

# Import db inside functions to avoid circular imports
def get_db():
    from src.database import db
    return db

class Project(get_db().Model):
    __tablename__ = 'project'
    
    id = get_db().Column(get_db().Integer, primary_key=True)
    title = get_db().Column(get_db().String(200), nullable=False)
    description = get_db().Column(get_db().Text)
    user_id = get_db().Column(get_db().Integer, get_db().ForeignKey('user.id'), nullable=False)
    status = get_db().Column(get_db().String(50), default='draft')  # draft, processing, completed, failed
    workflow_type = get_db().Column(get_db().String(50), default='assembler')  # assembler, generative
    script = get_db().Column(get_db().Text)
    transcript = get_db().Column(get_db().Text)  # JSON list of {word,start,end}
    video_url = get_db().Column(get_db().String(500))
    voice_type = get_db().Column(get_db().String(50), default='female')  # female, male, neutral
    created_at = get_db().Column(get_db().DateTime, default=datetime.utcnow)
    updated_at = get_db().Column(get_db().DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Simple relationship with user (no back_populates to avoid circular imports)
    # user = get_db().relationship('User', back_populates='projects')
    # Simple relationship with tasks (no back_populates to avoid circular imports)
    # tasks = get_db().relationship('Task', back_populates='project', cascade='all, delete-orphan')
    # Simple relationship with media assets (no back_populates to avoid circular imports)
    # media_assets = get_db().relationship('MediaAsset', back_populates='project', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Project {self.title}>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'user_id': self.user_id,
            'status': self.status,
            'workflow_type': self.workflow_type,
            'script': self.script,
            'video_url': self.video_url,
            'voice_type': self.voice_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }