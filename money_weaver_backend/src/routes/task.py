from flask import Blueprint, jsonify, request
from src.models.task import Task
from src.models.project import Project
from src.database import db
from src.auth import auth_required

task_bp = Blueprint('task', __name__)

@task_bp.route('/tasks', methods=['GET'])
@auth_required
def get_tasks():
    project_id = request.args.get('project_id')
    if project_id:
        tasks = Task.query.filter_by(project_id=project_id).all()
    else:
        tasks = Task.query.all()
    return jsonify([task.to_dict() for task in tasks])

@task_bp.route('/tasks', methods=['POST'])
@auth_required
def create_task():
    data = request.json
    
    # Validate project exists
    project = Project.query.get(data['project_id'])
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    task = Task(
        project_id=data['project_id'],
        task_type=data['task_type'],
        status=data.get('status', 'pending'),
        celery_task_id=data.get('celery_task_id')
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201

@task_bp.route('/tasks/<int:task_id>', methods=['GET'])
@auth_required
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    return jsonify(task.to_dict())

@task_bp.route('/tasks/<int:task_id>', methods=['PUT'])
@auth_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    data = request.json
    
    task.status = data.get('status', task.status)
    task.progress = data.get('progress', task.progress)
    task.result = data.get('result', task.result)
    task.error_message = data.get('error_message', task.error_message)
    task.celery_task_id = data.get('celery_task_id', task.celery_task_id)
    
    db.session.commit()
    return jsonify(task.to_dict())

@task_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
@auth_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return '', 204

@task_bp.route('/tasks/<int:task_id>/status', methods=['GET'])
@auth_required
def get_task_status(task_id):
    task = Task.query.get_or_404(task_id)
    return jsonify({
        'id': task.id,
        'status': task.status,
        'progress': task.progress,
        'error_message': task.error_message
    })

