import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, field_validator
from werkzeug.utils import secure_filename

from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.project import Project
from src.models.task import Task
from src.models.voice import Voice
from src.tasks.video_tasks import (
    batch_mix_videos_task,
    clone_voice_task,
    detect_viral_clips_task,
    generate_assembler_video_task,
    generate_generative_video_task,
)
from src.validation import require_fields
from src.services.llm_service import llm_service

router = APIRouter(prefix='/api', tags=['generation'])

UPLOAD_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


class AssemblerRequest(BaseModel):
    project_id: int
    prompt: str
    duration: Optional[int] = None
    orientation: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    voice_type: Optional[str] = None
    voice_id: Optional[int] = None
    niche_id: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None


class GenerativeRequest(BaseModel):
    project_id: int
    prompt: str
    voice_id: Optional[int] = None
    model: Optional[str] = None


class BatchMixRequest(BaseModel):
    project_id: int
    variations: list


class ClipDetectRequest(BaseModel):
    video_key: str
    count: Optional[int] = None
    project_id: Optional[int] = None

    @field_validator('count', mode='before')
    @classmethod
    def _reject_bool_count(cls, v):
        # Pydantic lax mode coerces True -> 1 for int fields, so a JSON
        # `true` would silently become count=1. Reject bools up front (422).
        if isinstance(v, bool):
            raise ValueError('count must be a positive integer')
        return v


def _coerce_clip_count(value):
    """Return a positive-int clip count (default 5) or raise ValueError.

    Rejects bools explicitly: isinstance(True, int) is True in Python, so a
    JSON `true` would otherwise slip through as count=1.
    """
    if value is None:
        return 5
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError('count must be a positive integer')
    return value


def _resolve_owned_voice(session, voice_id, user_id):
    """Coerce a payload voice_id and verify the caller owns that Voice.

    Returns (voice_or_None, error_response_or_None) where error_response is a
    (dict, status_code) tuple. The task re-checks ownership at run time; this
    gives the caller fast feedback (400/404/403) before anything is queued.
    """
    if voice_id is None:
        return None, None
    try:
        voice_id = int(voice_id)
    except (TypeError, ValueError):
        return None, ({'error': 'voice_id must be an integer'}, 400)
    voice = session.get(Voice, voice_id)
    if not voice:
        return None, ({'error': 'Voice not found'}, 404)
    if voice.user_id != user_id:
        return None, ({'error': 'Forbidden'}, 403)
    return voice, None


def _enqueue_assembler(body: dict, user, db, model=None):
    """Shared helper to enqueue an assembler video task.

    Sets task.generation_type = 'assembler' and calls
    generate_assembler_video_task.delay().
    """
    data = {**body}
    data['generation_type'] = 'assembler'

    try:
        require_fields(data, ['project_id', 'prompt'])
    except ValueError as e:
        raise HTTPException(400, str(e))

    project = db.get(Project, data['project_id'])
    if not project:
        raise HTTPException(404, 'Project not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')

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

    # Optional cloned voice owned by the caller
    voice_id = data.get('voice_id')
    voice, error = _resolve_owned_voice(db, voice_id, user.id)
    if error:
        raise HTTPException(error[1], error[0]['error'])

    # Create a task for tracking before queueing the Celery task
    task = Task(
        project_id=project.id,
        task_type='assembler_video_generation',
        status='pending',
        generation_type='assembler'
    )
    db.add(task)
    db.commit()

    # Optional niche — validate to guard path traversal (ValueError -> 400)
    niche_id = data.get('niche_id')
    if niche_id is not None:
        import re

        if not re.fullmatch(r"[a-z0-9_-]{1,32}", str(niche_id)):
            raise HTTPException(status_code=400, detail="invalid niche_id")

    # Optional completion webhook. A URL without a signing secret would let
    # anyone spoof callbacks, so the secret is mandatory when a URL is set.
    webhook_url = data.get('webhook_url')
    webhook_secret = data.get('webhook_secret')
    if webhook_url and not webhook_secret:
        raise HTTPException(400, 'webhook_secret is required when webhook_url is set')

    # Queue Celery task for assembler workflow with video settings
    try:
        celery_task = generate_assembler_video_task.delay(
            project_id=project.id,
            prompt=data['prompt'],
            duration=duration,
            orientation=orientation,
            width=width,
            height=height,
            voice_id=voice.id if voice else None,
            model=model,
            niche_id=niche_id,
            webhook_url=webhook_url,
            webhook_secret=webhook_secret,
        )
    except Exception as e:
        db.delete(task)
        db.commit()
        raise HTTPException(503, f'Task queue unavailable: {e}')

    # Update project status and voice type
    project.status = 'processing'
    project.workflow_type = 'assembler'
    project.voice_type = voice_type
    db.commit()

    # Associate the Celery task id with the tracking task
    task.celery_task_id = celery_task.id
    db.commit()

    return {
        'message': 'Video generation started',
        'task_id': task.id,
        'celery_task_id': celery_task.id,
        'project_id': project.id,
        'generation_type': 'assembler',
        'settings': {
            'duration': duration,
            'orientation': orientation,
            'width': width,
            'height': height,
            'voice_id': voice.id if voice else None
        }
    }


@router.post('/generate/assembler', status_code=202)
def generate_assembler_video(body: AssemblerRequest,
                             user=Depends(current_user),
                             session=Depends(get_db)):
    return _enqueue_assembler(body.model_dump(exclude_unset=True), user, session)


@router.post('/generate/generative', status_code=202)
def generate_generative_video(body: GenerativeRequest,
                              user=Depends(current_user),
                              session=Depends(get_db)):
    data = body.model_dump(exclude_unset=True)

    try:
        require_fields(data, ['project_id', 'prompt'])
    except ValueError as e:
        raise HTTPException(400, str(e))

    project = session.get(Project, data['project_id'])
    if not project:
        raise HTTPException(404, 'Project not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')

    # Optional cloned voice owned by the caller
    voice_id = data.get('voice_id')
    voice, error = _resolve_owned_voice(session, voice_id, user.id)
    if error:
        raise HTTPException(error[1], error[0]['error'])

    # Create a task for tracking before queueing the Celery task
    task = Task(
        project_id=project.id,
        task_type='generative_video_generation',
        status='pending'
    )
    session.add(task)
    session.commit()

    # Queue Celery task for generative workflow
    try:
        celery_task = generate_generative_video_task.delay(
            project_id=project.id,
            prompt=data['prompt'],
            voice_id=voice.id if voice else None,
            model=data.get('model')
        )
    except Exception as e:
        session.delete(task)
        session.commit()
        raise HTTPException(503, f'Task queue unavailable: {e}')

    # Update project status
    project.status = 'processing'
    project.workflow_type = 'generative'
    session.commit()

    # Associate the Celery task id with the tracking task
    task.celery_task_id = celery_task.id
    session.commit()

    return {
        'message': 'Generative video generation started',
        'task_id': task.id,
        'celery_task_id': celery_task.id,
        'project_id': project.id
    }


@router.post('/batch-mix', status_code=202)
def batch_mix_videos(body: BatchMixRequest,
                     user=Depends(current_user),
                     session=Depends(get_db)):
    data = body.model_dump(exclude_unset=True)

    try:
        require_fields(data, ['project_id', 'variations'])
    except ValueError as e:
        raise HTTPException(400, str(e))

    project = session.get(Project, data['project_id'])
    if not project:
        raise HTTPException(404, 'Project not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')

    # Create a task for tracking before queueing the Celery task
    task = Task(
        project_id=project.id,
        task_type='batch_mix_generation',
        status='pending'
    )
    session.add(task)
    session.commit()

    # Queue Celery task for batch mixing
    try:
        celery_task = batch_mix_videos_task.delay(
            project_id=project.id, variations=data['variations'])
    except Exception as e:
        session.delete(task)
        session.commit()
        raise HTTPException(503, f'Task queue unavailable: {e}')

    # Update project status
    project.status = 'processing'
    session.commit()

    # Associate the Celery task id with the tracking task
    task.celery_task_id = celery_task.id
    session.commit()

    return {
        'message': 'Batch mixing started',
        'task_id': task.id,
        'celery_task_id': celery_task.id,
        'project_id': project.id,
        'variations_count': len(data['variations'])
    }


@router.post('/generate/surprise', status_code=202)
def generate_surprise_video(
    seed: Optional[int] = None,
    voice_id: Optional[int] = None,
    preset_id: Optional[int] = None,
    duration: Optional[int] = None,
    orientation: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    user=Depends(current_user),
    session=Depends(get_db),
    model: Optional[str] = None,
):
    body = {
        'seed': seed,
        'voice_id': voice_id,
        'preset_id': preset_id,
        'duration': duration,
        'orientation': orientation,
        'width': width,
        'height': height,
    }
    prompt = llm_service.generate_idea(seed=body.get('seed'), model=model)['topic']
    if 'project_id' not in body:
        project = Project(
            title='Surprise Video',
            description='Surprise-generated video',
            user_id=user.id,
            workflow_type='assembler'
        )
        session.add(project)
        session.commit()
        body['project_id'] = project.id
    return _enqueue_assembler({**body, 'prompt': prompt}, user, session, model=model)


@router.post('/clips/detect', status_code=202)
def detect_clips(body: ClipDetectRequest,
                 user=Depends(current_user),
                 session=Depends(get_db)):
    """Queue viral-moment detection + clip extraction for an uploaded video."""
    data = body.model_dump(exclude_unset=True)

    try:
        require_fields(data, ['video_key', 'project_id'])
    except ValueError as e:
        raise HTTPException(400, str(e))

    project = session.get(Project, data['project_id'])
    if not project:
        raise HTTPException(404, 'Project not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')

    try:
        count = _coerce_clip_count(data.get('count'))
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Create a task for tracking before queueing the Celery task
    task = Task(
        project_id=project.id,
        task_type='viral_clip_detection',
        status='pending'
    )
    session.add(task)
    session.commit()

    try:
        celery_task = detect_viral_clips_task.delay(
            project_id=project.id, video_key=data['video_key'], count=count)
    except Exception as e:
        session.delete(task)
        session.commit()
        raise HTTPException(503, f'Task queue unavailable: {e}')

    # Associate the Celery task id with the tracking task
    task.celery_task_id = celery_task.id
    session.commit()

    return {
        'message': 'Viral clip detection started',
        'task_id': task.id,
        'celery_task_id': celery_task.id,
        'project_id': project.id,
        'count': count
    }


@router.get('/task-status/{task_id}')
def get_task_status(task_id: str,
                    user=Depends(current_user),
                    session=Depends(get_db)):
    """Get the status of a Celery task"""
    from src.services.celery_app import celery_app

    task = session.query(Task).filter_by(celery_task_id=task_id).first()
    if not task:
        raise HTTPException(404, 'Task not found')
    project = session.get(Project, task.project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')

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

    return response


@router.post('/clone-voice', status_code=202)
async def clone_voice(audio: UploadFile = File(None),
                      text: str = Form(''),
                      user=Depends(current_user),
                      session=Depends(get_db)):
    """Clone a voice from reference audio"""
    try:
        # Check if audio file is provided
        if audio is None:
            raise HTTPException(400, 'No audio file provided')

        if audio.filename == '':
            raise HTTPException(400, 'No audio file selected')

        # Save the audio file
        filename = secure_filename(audio.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        data = await audio.read()
        with open(filepath, 'wb') as fh:
            fh.write(data)

        # Get text from form data
        if not text:
            if os.path.exists(filepath):
                os.remove(filepath)
            raise HTTPException(400, 'Text is required for voice cloning')

        # Create a project for the cloned voice
        project = Project(
            title=f"Voice Clone - {filename}",
            description="Voice cloned from reference audio",
            user_id=user.id,
            workflow_type='voice_cloning'
        )
        session.add(project)
        session.commit()

        # Create a task for tracking before queueing the Celery task
        task = Task(
            project_id=project.id,
            task_type='voice_cloning',
            status='pending'
        )
        session.add(task)
        session.commit()

        # Queue Celery task for voice cloning
        try:
            celery_task = clone_voice_task.delay(
                reference_audio_path=filepath, text=text, project_id=project.id)
        except Exception as e:
            session.delete(task)
            session.delete(project)
            session.commit()
            if os.path.exists(filepath):
                os.remove(filepath)
            raise HTTPException(503, f'Task queue unavailable: {e}')

        # Associate the Celery task id with the tracking task
        task.celery_task_id = celery_task.id
        session.commit()

        return {
            'message': 'Voice cloning started',
            'task_id': task.id,
            'celery_task_id': celery_task.id,
            'project_id': project.id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f'Voice cloning failed: {e}')
