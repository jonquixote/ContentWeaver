"""YouTube OAuth + private upload endpoints (Task 8)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.project import Project
from src.models.task import Task
from src.services.providers import youtube_uploader
from src.tasks.video_tasks import youtube_upload_task

router = APIRouter(prefix='/api/youtube', tags=['youtube'])

ALLOWED_PRIVACY = ('private', 'unlisted', 'public')


class YoutubeUploadRequest(BaseModel):
    project_id: int
    privacy: str = 'private'

    @field_validator('privacy')
    @classmethod
    def _privacy_allowed(cls, v):
        if v not in ALLOWED_PRIVACY:
            raise ValueError(f'privacy must be one of {", ".join(ALLOWED_PRIVACY)}')
        return v


@router.get('/auth-url')
def youtube_auth_url(user=Depends(current_user)):
    """Consent URL for connecting the caller's YouTube channel."""
    try:
        url = youtube_uploader.get_auth_url(user.id)
    except RuntimeError as exc:
        # Missing client secret / libs is an environment problem.
        raise HTTPException(503, str(exc))
    return {'url': url}


@router.get('/callback')
def youtube_callback(code: str,
                     state: str,
                     session=Depends(get_db)):
    """OAuth redirect target.

    Google's browser redirect carries no bearer header, so current_user
    cannot gate this endpoint. The signed-in user id travels as an
    HMAC-signed OAuth `state` value (CSRF guard); the signature is verified
    before the embedded user id is trusted, then it must reference a real
    user.
    """
    try:
        user_id = youtube_uploader.verify_state(state)
    except ValueError:
        raise HTTPException(401, 'Invalid state')
    from src.models.user import User
    if session.get(User, user_id) is None:
        raise HTTPException(401, 'Unknown state')
    try:
        youtube_uploader.handle_callback(code, user_id)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    return {'message': 'YouTube connected'}


@router.post('/upload', status_code=202)
def youtube_upload(body: YoutubeUploadRequest,
                   user=Depends(current_user),
                   session=Depends(get_db)):
    """Queue a private YouTube upload of the project's rendered video."""
    project = session.get(Project, body.project_id)
    if not project:
        raise HTTPException(404, 'Project not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')

    task = Task(
        project_id=project.id,
        task_type='youtube_upload',
        status='pending',
    )
    session.add(task)
    session.commit()

    try:
        celery_task = youtube_upload_task.delay(
            project_id=project.id, privacy=body.privacy)
    except Exception as e:
        session.delete(task)
        session.commit()
        raise HTTPException(503, f'Task queue unavailable: {e}')

    task.celery_task_id = celery_task.id
    session.commit()

    return {
        'message': 'YouTube upload started',
        'task_id': task.id,
        'celery_task_id': celery_task.id,
        'project_id': project.id,
        'privacy': body.privacy,
    }
