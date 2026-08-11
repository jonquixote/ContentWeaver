from flask import Blueprint, jsonify, request
from src.models.project import Project
from src.models.user import User
from src.database import db
from src.auth import auth_required

project_bp = Blueprint('project', __name__)

@project_bp.route('/projects', methods=['GET'])
@auth_required
def get_projects():
    user_id = request.args.get('user_id')
    if user_id:
        projects = Project.query.filter_by(user_id=user_id).all()
    else:
        projects = Project.query.all()
    return jsonify([project.to_dict() for project in projects])

@project_bp.route('/projects', methods=['POST'])
@auth_required
def create_project():
    data = request.json
    
    # Validate user exists
    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    project = Project(
        title=data['title'],
        description=data.get('description', ''),
        user_id=data['user_id'],
        workflow_type=data.get('workflow_type', 'assembler')
    )
    db.session.add(project)
    db.session.commit()
    return jsonify(project.to_dict()), 201

@project_bp.route('/projects/<int:project_id>', methods=['GET'])
@auth_required
def get_project(project_id):
    project = Project.query.get_or_404(project_id)
    return jsonify(project.to_dict())

@project_bp.route('/projects/<int:project_id>', methods=['PUT'])
@auth_required
def update_project(project_id):
    project = Project.query.get_or_404(project_id)
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
    db.session.delete(project)
    db.session.commit()
    return '', 204

