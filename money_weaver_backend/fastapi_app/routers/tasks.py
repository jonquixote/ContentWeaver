import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.project import Project
from src.models.task import Task
from src.validation import require_fields

router = APIRouter(prefix='/api/tasks', tags=['tasks'])


class TaskCreate(BaseModel):
    project_id: Optional[int] = None
    task_type: Optional[str] = None
    status: Optional[str] = 'pending'
    celery_task_id: Optional[str] = None


class TaskUpdate(BaseModel):
    status: Optional[str] = None
    progress: Optional[int] = None
    result: Optional[str] = None
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None


@router.get('')
def get_tasks(project_id: Optional[int] = None,
              user=Depends(current_user),
              session=Depends(get_db)):
    if not project_id:
        projects = session.query(Project).filter_by(user_id=user.id).all()
        project_ids = [p.id for p in projects]
        if not project_ids:
            return []
        tasks = session.query(Task).filter(Task.project_id.in_(project_ids)).order_by(Task.id.desc()).all()
        return [_resolve_result_media(task.to_dict()) for task in tasks]
    project = session.get(Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    tasks = session.query(Task).filter_by(project_id=project_id).order_by(Task.id.desc()).all()
    return [_resolve_result_media(task.to_dict()) for task in tasks]


@router.post('', status_code=201)
def create_task(body: TaskCreate, user=Depends(current_user), session=Depends(get_db)):
    data = body.model_dump()
    try:
        require_fields(data, ['project_id', 'task_type'])
    except ValueError as e:
        raise HTTPException(400, str(e))

    project = session.get(Project, data['project_id'])
    if not project:
        raise HTTPException(404, 'Project not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')

    task = Task(
        project_id=data['project_id'],
        task_type=data['task_type'],
        status=data.get('status', 'pending'),
        celery_task_id=data.get('celery_task_id')
    )
    session.add(task)
    session.commit()
    return task.to_dict()


@router.get('/{task_id}')
def get_task(task_id: int, user=Depends(current_user), session=Depends(get_db)):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(404, 'Not found')
    project = session.get(Project, task.project_id)
    if not project:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    return _resolve_result_media(task.to_dict())


@router.put('/{task_id}')
def update_task(task_id: int, body: TaskUpdate, user=Depends(current_user), session=Depends(get_db)):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(404, 'Not found')
    project = session.get(Project, task.project_id)
    if not project:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    data = body.model_dump(exclude_unset=True)
    try:
        require_fields(data, [])
    except ValueError as e:
        raise HTTPException(400, str(e))

    task.status = data.get('status', task.status)
    task.progress = data.get('progress', task.progress)
    task.result = data.get('result', task.result)
    task.error_message = data.get('error_message', task.error_message)
    task.celery_task_id = data.get('celery_task_id', task.celery_task_id)

    session.commit()
    return task.to_dict()


@router.delete('/{task_id}')
def delete_task(task_id: int, user=Depends(current_user), session=Depends(get_db)):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(404, 'Not found')
    project = session.get(Project, task.project_id)
    if not project:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    session.delete(task)
    session.commit()
    return Response(status_code=204)


@router.get('/{task_id}/status')
def get_task_status(task_id: int, user=Depends(current_user), session=Depends(get_db)):
    task = session.get(Task, task_id)
    if task is None:
        raise HTTPException(404, 'Not found')
    project = session.get(Project, task.project_id)
    if not project:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')

    result = None
    if task.result:
        try:
            result = json.loads(task.result)
        except (ValueError, TypeError):
            result = None

    video_url = None
    thumbnail_url = None
    if task.status == 'completed':
        stored_video = (result or {}).get('video_url') if isinstance(result, dict) else None
        stored_thumb = (result or {}).get('thumbnail_url') if isinstance(result, dict) else None
        video_url = _resolve_media_url(stored_video)
        thumbnail_url = _resolve_media_url(stored_thumb)

    if task.status == 'failed':
        message = task.error_message or 'Task failed'
    elif task.status == 'completed':
        message = 'Completed'
    else:
        message = _progress_message(task.progress)

    return {
        'id': task.id,
        'status': task.status,
        'progress': task.progress,
        'message': message,
        'video_url': video_url,
        'thumbnail_url': thumbnail_url,
        'error': task.error_message
    }


def _resolve_media_url(value):
    """Resolve a stored media value to a playable URL.

    Storage keys (videos/..., thumbs/...) are swapped for a fresh 1h presigned
    URL; legacy /final/... paths are returned unchanged. Falls back to the
    stored value on storage outage so the status endpoint never 500s.
    """
    if not value:
        return None
    if value.startswith('videos/') or value.startswith('thumbs/'):
        try:
            from src.services.storage import get_storage
            return get_storage().get_presigned_url(value)
        except Exception:
            return value
    return value


def _resolve_result_media(task_dict):
    """Resolve storage keys inside a task dict's `result` JSON.

    Mirrors the status route so list/detail endpoints return the same playable
    URLs (storage keys -> presigned URL; legacy /final/... unchanged). Reuses
    `_resolve_media_url`, which never raises on storage outage. Non-JSON or
    non-dict `result` values pass through untouched.
    """
    raw = task_dict.get('result')
    if not raw:
        return task_dict
    try:
        result = json.loads(raw)
    except (ValueError, TypeError):
        return task_dict
    if not isinstance(result, dict):
        return task_dict
    for key in ('video_url', 'thumbnail_url'):
        stored = result.get(key)
        resolved = _resolve_media_url(stored)
        if resolved != stored:
            result[key] = resolved
    task_dict['result'] = json.dumps(result)
    return task_dict


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