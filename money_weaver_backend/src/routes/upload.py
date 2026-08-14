import uuid

from flask import Blueprint, g, jsonify, request

from src.auth import auth_required
from src.services.storage import get_storage, is_valid_storage_key

upload_bp = Blueprint('uploads', __name__)

CONTENT_TYPES = {'wav': 'audio/wav', 'mp3': 'audio/mpeg'}
# Reference-audio cap enforced by validate_audio / the TTS service; reject at
# the proxy before buffering the whole body in RAM.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


@upload_bp.route('/uploads/presign', methods=['GET'])
@auth_required
def presign_upload():
    ext = (request.args.get('ext') or '').lower().strip().lstrip('.')
    if ext not in CONTENT_TYPES:
        return jsonify({'error': 'ext must be wav or mp3'}), 400

    # Mint the object key server-side; never trust a client-supplied path.
    key = f"voices/{g.current_user['id']}/{uuid.uuid4().hex}.{ext}"
    try:
        upload_url = get_storage().get_presigned_upload_url(
            key, expires=600, content_type=CONTENT_TYPES[ext])
    except Exception as e:
        return jsonify({'error': f'Failed to prepare upload: {e}'}), 500
    return jsonify({'upload_url': upload_url, 'object_key': key})


@upload_bp.route('/uploads/<path:path>', methods=['PUT'])
@auth_required
def put_upload(path):
    if not is_valid_storage_key(path, g.current_user['id']):
        return jsonify({'error': 'invalid upload path'}), 400
    if request.content_length is not None and request.content_length > MAX_UPLOAD_BYTES:
        return jsonify({'error': 'upload body exceeds the 25MB cap'}), 413
    data = request.get_data()
    if not data:
        return jsonify({'error': 'empty upload body'}), 400
    if len(data) > MAX_UPLOAD_BYTES:
        return jsonify({'error': 'upload body exceeds the 25MB cap'}), 413
    ext = path.rsplit('.', 1)[1].lower()
    try:
        get_storage().put_object(path, data, CONTENT_TYPES[ext])
    except Exception as e:
        return jsonify({'error': f'Upload failed: {e}'}), 500
    return jsonify({'ok': True, 'object_key': path})