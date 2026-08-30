import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.project import Project
from src.validation import require_fields

router = APIRouter(prefix='/api/projects', tags=['projects'])


class ProjectCreate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = ''
    workflow_type: Optional[str] = 'assembler'


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    workflow_type: Optional[str] = None
    script: Optional[str] = None
    video_url: Optional[str] = None


def _resolve_video_url(value):
    """Swap a storage key (videos/...) for a fresh presigned URL; leave legacy
    /final/... paths untouched. Returns the key itself on storage outage."""
    if not value:
        return value
    if value.startswith('videos/') or value.startswith('thumbs/'):
        try:
            from src.services.storage import get_storage
            return get_storage().get_presigned_url(value)
        except Exception:
            return value
    return value


def _project_dict(project):
    d = project.to_dict()
    d['video_url'] = _resolve_video_url(d['video_url'])
    return d


@router.get('')
def get_projects(user=Depends(current_user), session=Depends(get_db)):
    projects = session.query(Project).filter_by(user_id=user.id).all()
    return [_project_dict(project) for project in projects]


@router.post('', status_code=201)
def create_project(body: ProjectCreate, user=Depends(current_user), session=Depends(get_db)):
    data = body.model_dump()
    try:
        require_fields(data, ['title'])
    except ValueError as e:
        raise HTTPException(400, str(e))
    project = Project(
        title=data['title'],
        description=data.get('description', ''),
        user_id=user.id,
        workflow_type=data.get('workflow_type', 'assembler')
    )
    session.add(project)
    session.commit()
    return project.to_dict()


@router.post('/studio', status_code=201)
def create_studio_draft(user=Depends(current_user), session=Depends(get_db)):
    project = Project(title='Studio Draft', description='',
                      user_id=user.id, workflow_type='assembler')
    session.add(project)
    session.commit()
    return project.to_dict()


@router.get('/{project_id}')
def get_project(project_id: int, user=Depends(current_user), session=Depends(get_db)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    return _project_dict(project)


@router.put('/{project_id}')
def update_project(project_id: int, body: ProjectUpdate, user=Depends(current_user), session=Depends(get_db)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    data = body.model_dump(exclude_unset=True)
    try:
        require_fields(data, [])
    except ValueError as e:
        raise HTTPException(400, str(e))
    project.title = data.get('title', project.title)
    project.description = data.get('description', project.description)
    project.status = data.get('status', project.status)
    project.workflow_type = data.get('workflow_type', project.workflow_type)
    project.script = data.get('script', project.script)
    project.video_url = data.get('video_url', project.video_url)
    session.commit()
    return project.to_dict()


@router.delete('/{project_id}')
def delete_project(project_id: int, user=Depends(current_user), session=Depends(get_db)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    session.delete(project)
    session.commit()
    return Response(status_code=204)


@router.get('/{project_id}/studio')
def get_studio_state(project_id: int, user=Depends(current_user), session=Depends(get_db)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    if project.studio_state is None:
        raise HTTPException(404, 'No studio draft')
    return {'studio_state': json.loads(project.studio_state)}


@router.put('/{project_id}/studio')
def put_studio_state(project_id: int, body: dict,
                     user=Depends(current_user), session=Depends(get_db)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    project.studio_state = json.dumps(body)
    project.schema_version = int(body.get('schemaVersion', project.schema_version or 1))
    # Keep the real Project.title in sync with the studio script title so the
    # dashboard list and /projects/:id reflect what the user actually named it.
    script_title = (body.get('script') or {}).get('title')
    if script_title and str(script_title).strip():
        project.title = str(script_title).strip()
    session.commit()
    return {'saved_at': datetime.now(timezone.utc).isoformat()}