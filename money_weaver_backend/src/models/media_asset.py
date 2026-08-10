from datetime import datetime

# Import db inside functions to avoid circular imports
def get_db():
    from src.database import db
    return db

class MediaAsset(get_db().Model):
    __tablename__ = 'media_asset'
    
    id = get_db().Column(get_db().Integer, primary_key=True)
    project_id = get_db().Column(get_db().Integer, get_db().ForeignKey('project.id'), nullable=False)
    filename = get_db().Column(get_db().String(255), nullable=False)
    file_path = get_db().Column(get_db().String(500), nullable=False)  # Path in MinIO or local storage
    file_type = get_db().Column(get_db().String(50), nullable=False)  # video, audio, image, subtitle
    file_size = get_db().Column(get_db().Integer)  # Size in bytes
    duration = get_db().Column(get_db().Float)  # Duration in seconds (for video/audio)
    asset_metadata = get_db().Column(get_db().Text)  # JSON metadata
    created_at = get_db().Column(get_db().DateTime, default=datetime.utcnow)
    
    # Simple relationship with project (no back_populates to avoid circular imports)
    # project = get_db().relationship('Project', back_populates='media_assets')

    def __repr__(self):
        return f'<MediaAsset {self.filename}>'

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'filename': self.filename,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'duration': self.duration,
            'metadata': self.asset_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

