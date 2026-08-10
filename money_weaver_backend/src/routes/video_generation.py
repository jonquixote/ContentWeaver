from flask import Blueprint, jsonify, request
from src.models.project import Project
from src.models.task import Task
from src.database import db
from src.tasks.video_tasks import generate_assembler_video_task, generate_generative_video_task, batch_mix_videos_task

video_bp = Blueprint('video', __name__)

@video_bp.route('/generate/assembler', methods=['POST'])
def generate_assembler_video():
    """Generate video using the assembler workflow (stock footage + TTS)"""
    data = request.json
    
    # Validate required fields
    if not data.get('project_id') or not data.get('prompt'):
        return jsonify({'error': 'project_id and prompt are required'}), 400
    
    project = Project.query.get(data['project_id'])
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    # Extract video settings from request data
    duration = data.get('duration', 30)  # Default to 30 seconds
    orientation = data.get('orientation', 'landscape')  # Default to landscape
    width = data.get('width', 1920)  # Default to 1920 pixels
    height = data.get('height', 1080)  # Default to 1080 pixels
    voice_type = data.get('voice_type', 'female')  # Default to female voice
    
    # Validate duration
    if not isinstance(duration, int) or duration <= 0:
        duration = 30
    
    # Validate orientation
    if orientation not in ['landscape', 'portrait', 'square']:
        orientation = 'landscape'
    
    # Validate resolution
    if not isinstance(width, int) or width <= 0:
        width = 1920
    
    if not isinstance(height, int) or height <= 0:
        height = 1080
    
    # Update project status and voice type
    project.status = 'processing'
    project.workflow_type = 'assembler'
    project.voice_type = voice_type
    db.session.commit()
    
    # Queue Celery task for assembler workflow with video settings
    celery_task = generate_assembler_video_task.delay(
        project.id, 
        data['prompt'],
        duration=duration,
        orientation=orientation,
        width=width,
        height=height
    )
    
    # Create a task for tracking
    task = Task(
        project_id=project.id,
        task_type='assembler_video_generation',
        status='pending',
        celery_task_id=celery_task.id
    )
    db.session.add(task)
    db.session.commit()
    
    return jsonify({
        'message': 'Video generation started',
        'task_id': task.id,
        'celery_task_id': celery_task.id,
        'project_id': project.id,
        'settings': {
            'duration': duration,
            'orientation': orientation,
            'width': width,
            'height': height
        }
    }), 202

@video_bp.route('/generate/generative', methods=['POST'])
def generate_generative_video():
    """Generate video using the generative workflow (ComfyUI)"""
    data = request.json
    
    # Validate required fields
    if not data.get('project_id') or not data.get('prompt'):
        return jsonify({'error': 'project_id and prompt are required'}), 400
    
    project = Project.query.get(data['project_id'])
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    # Update project status
    project.status = 'processing'
    project.workflow_type = 'generative'
    db.session.commit()
    
    # Queue Celery task for generative workflow
    celery_task = generate_generative_video_task.delay(project.id, data['prompt'])
    
    # Create a task for tracking
    task = Task(
        project_id=project.id,
        task_type='generative_video_generation',
        status='pending',
        celery_task_id=celery_task.id
    )
    db.session.add(task)
    db.session.commit()
    
    return jsonify({
        'message': 'Generative video generation started',
        'task_id': task.id,
        'celery_task_id': celery_task.id,
        'project_id': project.id
    }), 202

@video_bp.route('/batch-mix', methods=['POST'])
def batch_mix_videos():
    """Generate multiple video variations using batch mixing"""
    data = request.json
    
    # Validate required fields
    if not data.get('project_id') or not data.get('variations'):
        return jsonify({'error': 'project_id and variations are required'}), 400
    
    project = Project.query.get(data['project_id'])
    if not project:
        return jsonify({'error': 'Project not found'}), 404
    
    # Update project status
    project.status = 'processing'
    db.session.commit()
    
    # Queue Celery task for batch mixing
    celery_task = batch_mix_videos_task.delay(project.id, data['variations'])
    
    # Create a task for tracking
    task = Task(
        project_id=project.id,
        task_type='batch_mix_generation',
        status='pending',
        celery_task_id=celery_task.id
    )
    db.session.add(task)
    db.session.commit()
    
    return jsonify({
        'message': 'Batch mixing started',
        'task_id': task.id,
        'celery_task_id': celery_task.id,
        'project_id': project.id,
        'variations_count': len(data['variations'])
    }), 202

@video_bp.route('/task-status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    """Get the status of a Celery task"""
    from src.services.celery_app import celery_app
    
    try:
        task_result = celery_app.AsyncResult(task_id)
        
        if task_result.state == 'PENDING':
            response = {
                'state': task_result.state,
                'current': 0,
                'total': 1,
                'status': 'Pending...'
            }
        elif task_result.state == 'PROGRESS':
            # Handle progress information safely
            try:
                if hasattr(task_result, 'info') and task_result.info:
                    if isinstance(task_result.info, dict):
                        response = {
                            'state': task_result.state,
                            'current': task_result.info.get('current', 0),
                            'total': task_result.info.get('total', 1),
                            'status': task_result.info.get('status', '')
                        }
                        if 'result' in task_result.info:
                            response['result'] = task_result.info['result']
                    else:
                        response = {
                            'state': task_result.state,
                            'current': 0,
                            'total': 1,
                            'status': str(task_result.info)
                        }
                else:
                    response = {
                        'state': task_result.state,
                        'current': 0,
                        'total': 1,
                        'status': 'In progress...'
                    }
            except Exception as e:
                response = {
                    'state': task_result.state,
                    'current': 0,
                    'total': 1,
                    'status': f'Progress info unavailable: {str(e)}'
                }
        elif task_result.state == 'SUCCESS':
            response = {
                'state': task_result.state,
                'current': 100,
                'total': 100,
                'status': 'Completed successfully!',
                'result': task_result.result
            }
        elif task_result.state == 'FAILURE':
            # Handle failure information safely
            try:
                # Safely extract error information
                if hasattr(task_result, 'info') and task_result.info:
                    if isinstance(task_result.info, dict):
                        response = {
                            'state': task_result.state,
                            'current': 0,
                            'total': 1,
                            'status': task_result.info.get('status', str(task_result.info))
                        }
                    elif isinstance(task_result.info, Exception):
                        response = {
                            'state': task_result.state,
                            'current': 0,
                            'total': 1,
                            'status': str(task_result.info)
                        }
                    else:
                        response = {
                            'state': task_result.state,
                            'current': 0,
                            'total': 1,
                            'status': str(task_result.info)
                        }
                else:
                    # Try to get exception information from traceback
                    response = {
                        'state': task_result.state,
                        'current': 0,
                        'total': 1,
                        'status': 'Task failed - check logs for details'
                    }
            except Exception as e:
                response = {
                    'state': 'FAILURE',
                    'current': 0,
                    'total': 1,
                    'status': f'Task failed with error: {str(e)}'
                }
        else:
            # Handle any other states
            response = {
                'state': task_result.state,
                'current': 0,
                'total': 1,
                'status': f'Status: {task_result.state}'
            }
    except Exception as e:
        # Handle any errors in retrieving task status
        response = {
            'state': 'ERROR',
            'current': 0,
            'total': 1,
            'status': f'Error retrieving task status: {str(e)}'
        }
    
    return jsonify(response)


@video_bp.route('/voices', methods=['GET'])
def get_available_voices():
    """Get list of available voices"""
    try:
        from src.services.video.advanced_tts_service import advanced_tts_service
        
        voices = {
            'female': advanced_tts_service.available_voices.get('female', []),
            'male': advanced_tts_service.available_voices.get('male', []),
            'default': advanced_tts_service.available_voices.get('default', 'af_heart')
        }
        
        return jsonify({
            'voices': voices,
            'status': 'success'
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

