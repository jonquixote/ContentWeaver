from flask import Blueprint, jsonify, request, g
from src.models.template import VideoTemplate
from src.database import db
from src.auth import auth_required

templates_bp = Blueprint('templates', __name__)


@templates_bp.route('/templates', methods=['GET'])
@auth_required
def get_templates():
    user_id = g.current_user['id']
    templates = VideoTemplate.query.filter(
        (VideoTemplate.user_id == user_id) | (VideoTemplate.is_public == True)  # noqa: E712
    ).order_by(VideoTemplate.created_at.desc()).all()
    return jsonify([template.to_dict() for template in templates])


@templates_bp.route('/templates', methods=['POST'])
@auth_required
def create_template():
    data = request.json
    if not isinstance(data, dict):
        return jsonify({'error': 'Request body must be a JSON object'}), 400
    if not data.get('name'):
        return jsonify({'error': 'Missing required fields: name'}), 400
    if 'config' not in data:
        return jsonify({'error': 'Missing required fields: config'}), 400
    if not isinstance(data['name'], str) or not (1 <= len(data['name']) <= 100):
        return jsonify({'error': 'name must be a string between 1 and 100 characters'}), 400
    if not isinstance(data['config'], dict):
        return jsonify({'error': 'config must be a JSON object'}), 400

    template = VideoTemplate(
        name=data['name'],
        description=data.get('description', ''),
        config=data['config'],
        is_public=bool(data.get('is_public', False)),
        user_id=g.current_user['id']
    )
    db.session.add(template)
    db.session.commit()
    return jsonify(template.to_dict()), 201


@templates_bp.route('/templates/<int:template_id>', methods=['GET'])
@auth_required
def get_template(template_id):
    template = VideoTemplate.query.get_or_404(template_id)
    if template.user_id != g.current_user['id'] and not template.is_public:
        return jsonify({'error': 'Forbidden'}), 403
    return jsonify(template.to_dict())


@templates_bp.route('/templates/<int:template_id>', methods=['PUT'])
@auth_required
def update_template(template_id):
    template = VideoTemplate.query.get_or_404(template_id)
    if template.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    data = request.json
    if not isinstance(data, dict):
        return jsonify({'error': 'Request body must be a JSON object'}), 400
    if 'name' in data and (not isinstance(data['name'], str) or not (1 <= len(data['name']) <= 100)):
        return jsonify({'error': 'name must be a string between 1 and 100 characters'}), 400
    if 'config' in data and not isinstance(data['config'], dict):
        return jsonify({'error': 'config must be a JSON object'}), 400

    template.name = data.get('name', template.name)
    template.description = data.get('description', template.description)
    if 'config' in data:
        template.config = data['config']
    if 'is_public' in data:
        template.is_public = bool(data['is_public'])

    db.session.commit()
    return jsonify(template.to_dict())


@templates_bp.route('/templates/<int:template_id>', methods=['DELETE'])
@auth_required
def delete_template(template_id):
    template = VideoTemplate.query.get_or_404(template_id)
    if template.user_id != g.current_user['id']:
        return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(template)
    db.session.commit()
    return '', 204
