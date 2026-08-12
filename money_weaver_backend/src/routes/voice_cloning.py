from flask import Blueprint, jsonify, request, g
from src.models.project import Project
from src.models.task import Task
from src.database import db
from src.tasks.video_tasks import clone_voice_task
from src.auth import auth_required
import os
from werkzeug.utils import secure_filename

voice_cloning_bp = Blueprint('voice_cloning', __name__)

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@voice_cloning_bp.route('/clone-voice', methods=['POST'])
@auth_required
def clone_voice():
    """Clone a voice from reference audio"""
    try:
        # Check if audio file is provided
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        if audio_file.filename == '':
            return jsonify({'error': 'No audio file selected'}), 400
        
        # Save the audio file
        filename = secure_filename(audio_file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        audio_file.save(filepath)
        
        # Get text from form data
        text = request.form.get('text', '')
        if not text:
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': 'Text is required for voice cloning'}), 400
        
        # Create a project for the cloned voice
        project = Project(
            title=f"Voice Clone - {filename}",
            description="Voice cloned from reference audio",
            user_id=g.current_user['id'],
            workflow_type='voice_cloning'
        )
        db.session.add(project)
        db.session.commit()

        # Create a task for tracking before queueing the Celery task
        task = Task(
            project_id=project.id,
            task_type='voice_cloning',
            status='pending'
        )
        db.session.add(task)
        db.session.commit()

        # Queue Celery task for voice cloning
        try:
            celery_task = clone_voice_task.delay(filepath, text, project.id)
        except Exception as e:
            db.session.rollback()
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': 'Task queue unavailable', 'details': str(e)}), 503

        # Associate the Celery task id with the tracking task
        task.celery_task_id = celery_task.id
        db.session.commit()
        
        return jsonify({
            'message': 'Voice cloning started',
            'task_id': task.id,
            'celery_task_id': celery_task.id,
            'project_id': project.id
        }), 202
        
    except Exception as e:
        return jsonify({'error': 'Voice cloning failed', 'details': str(e)}), 500