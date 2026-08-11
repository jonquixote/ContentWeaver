from flask import Blueprint, jsonify
from src.models.preset import FormatPreset
from src.auth import auth_required

presets_bp = Blueprint('presets', __name__)

@presets_bp.route('/presets', methods=['GET'])
@auth_required
def list_presets():
    presets = FormatPreset.query.order_by(FormatPreset.is_default.desc(), FormatPreset.name).all()
    return jsonify([p.to_dict() for p in presets])