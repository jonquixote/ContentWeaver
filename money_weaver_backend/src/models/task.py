from datetime import datetime

# Import db inside functions to avoid circular imports
def get_db():
    from src.database import db
    return db

class Task(get_db().Model):
    __tablename__ = 'task'
    
    id = get_db().Column(get_db().Integer, primary_key=True)
    project_id = get_db().Column(get_db().Integer, get_db().ForeignKey('project.id'), nullable=False)
    task_type = get_db().Column(get_db().String(100), nullable=False)  # script_generation, video_assembly, etc.
    status = get_db().Column(get_db().String(50), default='pending')  # pending, running, completed, failed
    progress = get_db().Column(get_db().Integer, default=0)  # 0-100
    result = get_db().Column(get_db().Text)  # JSON result data
    error_message = get_db().Column(get_db().Text)
    thumbnail_path = get_db().Column(get_db().String(500))
    celery_task_id = get_db().Column(get_db().String(255))  # Celery task ID for tracking
    created_at = get_db().Column(get_db().DateTime, default=datetime.utcnow)
    updated_at = get_db().Column(get_db().DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Simple relationship with project (no back_populates to avoid circular imports)
    # project = get_db().relationship('Project', back_populates='tasks')

    def __repr__(self):
        return f'<Task {self.task_type} for Project {self.project_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'task_type': self.task_type,
            'status': self.status,
            'progress': self.progress,
            'result': self.result,
            'error_message': self.error_message,
            'thumbnail_path': self.thumbnail_path,
            'celery_task_id': self.celery_task_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }