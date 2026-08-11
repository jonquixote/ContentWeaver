from flask import Blueprint, jsonify, request, g
from src.models.project import Project
from src.database import db
from src.auth import auth_required
from src.validation import require_fields

project_bp = Blueprint('project', __name__)

@project_bp.route('/projects', methods=['GET'])
@auth_required
def get_projects():
    projects = Project.query.filter_by(user_id=g.current_user['id']).all()
    return jsonify([project.to_dict() for project in projects])

@project_bp.route('/projects', methods=['POST'])
@auth_required
def create_project():
    data = request.json
    try:
        require_fields(data, ['title'])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    
    project = Project(
        title=data['title'],
        description=data.get('description', ''),
        user_id=g.current_user['id'],
        workflow_type=data.get('workflow_type', 'assembler')
    )
    db.session.add(project)
    db.session.commit()
    return jsonify(project.to_dict()), 201

@project_bp.route('/projects/<int:project_id>', methods=['GET'])
@auth_required
def get_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(project.to_dict())

@project_bp.route('/projects/<int:project_id>', methods=['PUT'])
@auth_required
def update_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.json
    
    project.title = data.get('title', project.title)
    project.description = data.get('description', project.description)
    project.status = data.get('status', project.status)
    project.workflow_type = data.get('workflow_type', project.workflow_type)
    project.script = data.get('script', project.script)
    project.video_url = data.get('video_url', project.video_url)
    
    db.session.commit()
    return jsonify(project.to_dict())

@project_bp.route('/projects/<int:project_id>', methods=['DELETE'])
@auth_required
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(project)
    db.session.commit()
    return '', 204

