from flask import Blueprint, jsonify, request, g
import json
from src.models.task import Task
from src.models.project import Project
from src.database import db
from src.auth import auth_required
from src.validation import require_fields

task_bp = Blueprint('task', __name__)

@task_bp.route('/tasks', methods=['GET'])
@auth_required
def get_tasks():
    project_id = request.args.get('project_id')
    if not project_id:
        projects = Project.query.filter_by(user_id=g.current_user['id']).all()
        project_ids = [p.id for p in projects]
        if not project_ids:
            return jsonify([])
        tasks = Task.query.filter(Task.project_id.in_(project_ids)).order_by(Task.id.desc()).all()
        return jsonify([task.to_dict() for task in tasks])
    project = Project.query.get(project_id)
    if not project or project.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    tasks = Task.query.filter_by(project_id=project_id).order_by(Task.id.desc()).all()
    return jsonify([task.to_dict() for task in tasks])

@task_bp.route('/tasks', methods=['POST'])
@auth_required
def create_task():
    data = request.json
    try:
        require_fields(data, ['project_id', 'task_type'])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
    # Validate project exists and belongs to user
    project = Project.query.get(data['project_id'])
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    if project.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    
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
    project = Project.query.get(task.project_id)
    if not project:
        return jsonify({'error': 'Not found'}), 404
    if project.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(task.to_dict())

@task_bp.route('/tasks/<int:task_id>', methods=['PUT'])
@auth_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get(task.project_id)
    if not project:
        return jsonify({'error': 'Not found'}), 404
    if project.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.json
    try:
        require_fields(data, [])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
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
    project = Project.query.get(task.project_id)
    if not project:
        return jsonify({'error': 'Not found'}), 404
    if project.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(task)
    db.session.commit()
    return '', 204

@task_bp.route('/tasks/<int:task_id>/status', methods=['GET'])
@auth_required
def get_task_status(task_id):
    task = Task.query.get_or_404(task_id)
    project = Project.query.get(task.project_id)
    if not project:
        return jsonify({'error': 'Not found'}), 404
    if project.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403

    result = None
    if task.result:
        try:
            result = json.loads(task.result)
        except (ValueError, TypeError):
            result = None

    video_url = (result or {}).get('video_url') if isinstance(result, dict) else None
    thumbnail_url = (result or {}).get('thumbnail_url') if isinstance(result, dict) else None

    if task.status == 'failed':
        message = task.error_message or 'Task failed'
    elif task.status == 'completed':
        message = 'Completed'
    else:
        message = _progress_message(task.progress)

    return jsonify({
        'id': task.id,
        'status': task.status,
        'progress': task.progress,
        'message': message,
        'video_url': video_url,
        'thumbnail_url': thumbnail_url,
        'error': task.error_message
    })


def _progress_message(progress):
    """Map a progress percentage to a human message, matching the plan's status shape."""
    if progress < 10:
        return 'Queued...'
    if progress < 20:
        return 'Generating script...'
    if progress < 40:
        return 'Generating voiceover...'
    if progress < 80:
        return 'Searching for stock footage...'
    if progress < 90:
        return 'Assembling video...'
    if progress < 100:
        return 'Generating thumbnail...'
    return 'Completed'

