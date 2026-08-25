from datetime import datetime


# Import db inside functions to avoid circular imports
def get_db():
    from src.database import db
    return db


class ModelAssignment(get_db().Model):
    __tablename__ = 'model_assignment'
    __table_args__ = (
        get_db().UniqueConstraint('user_id', 'task', name='uq_model_assignment_user_task'),
    )

    id = get_db().Column(get_db().Integer, primary_key=True)
    user_id = get_db().Column(get_db().Integer, get_db().ForeignKey('user.id'), nullable=False)
    task = get_db().Column(get_db().String(32), nullable=False)
    model_id = get_db().Column(get_db().String(255), nullable=False)
    created_at = get_db().Column(get_db().DateTime, default=datetime.utcnow)
    updated_at = get_db().Column(get_db().DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'task': self.task,
            'model_id': self.model_id,
        }
