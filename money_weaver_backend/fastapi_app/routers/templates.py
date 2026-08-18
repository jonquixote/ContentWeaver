from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.template import VideoTemplate

router = APIRouter(prefix='/api/templates', tags=['templates'])


class TemplateCreate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = ''
    config: Optional[dict] = None
    is_public: Optional[bool] = False


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None
    is_public: Optional[bool] = None


@router.get('')
def get_templates(user=Depends(current_user), session=Depends(get_db)):
    user_id = user.id
    templates = session.query(VideoTemplate).filter(
        (VideoTemplate.user_id == user_id) | (VideoTemplate.is_public == True)  # noqa: E712
    ).order_by(VideoTemplate.created_at.desc()).all()
    return [template.to_dict() for template in templates]


@router.post('', status_code=201)
def create_template(body: TemplateCreate, user=Depends(current_user), session=Depends(get_db)):
    data = body.model_dump(exclude_unset=True)
    if not isinstance(data, dict):
        raise HTTPException(400, 'Request body must be a JSON object')
    if not data.get('name'):
        raise HTTPException(400, 'Missing required fields: name')
    if 'config' not in data:
        raise HTTPException(400, 'Missing required fields: config')
    if not isinstance(data['name'], str) or not (1 <= len(data['name']) <= 100):
        raise HTTPException(400, 'name must be a string between 1 and 100 characters')
    if not isinstance(data['config'], dict):
        raise HTTPException(400, 'config must be a JSON object')

    template = VideoTemplate(
        name=data['name'],
        description=data.get('description', ''),
        config=data['config'],
        is_public=bool(data.get('is_public', False)),
        user_id=user.id
    )
    session.add(template)
    session.commit()
    return template.to_dict()


@router.get('/{template_id}')
def get_template(template_id: int, user=Depends(current_user), session=Depends(get_db)):
    template = session.get(VideoTemplate, template_id)
    if template is None:
        raise HTTPException(404, 'Not found')
    if template.user_id != user.id and not template.is_public:
        raise HTTPException(403, 'Forbidden')
    return template.to_dict()


@router.put('/{template_id}')
def update_template(template_id: int, body: TemplateUpdate,
                    user=Depends(current_user), session=Depends(get_db)):
    template = session.get(VideoTemplate, template_id)
    if template is None:
        raise HTTPException(404, 'Not found')
    if template.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    data = body.model_dump(exclude_unset=True)
    if not isinstance(data, dict):
        raise HTTPException(400, 'Request body must be a JSON object')
    if 'name' in data and (not isinstance(data['name'], str) or not (1 <= len(data['name']) <= 100)):
        raise HTTPException(400, 'name must be a string between 1 and 100 characters')
    if 'config' in data and not isinstance(data['config'], dict):
        raise HTTPException(400, 'config must be a JSON object')

    template.name = data.get('name', template.name)
    template.description = data.get('description', template.description)
    if 'config' in data:
        template.config = data['config']
    if 'is_public' in data:
        template.is_public = bool(data['is_public'])

    session.commit()
    return template.to_dict()


@router.delete('/{template_id}')
def delete_template(template_id: int, user=Depends(current_user), session=Depends(get_db)):
    template = session.get(VideoTemplate, template_id)
    if template is None:
        raise HTTPException(404, 'Not found')
    if template.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    session.delete(template)
    session.commit()
    return Response(status_code=204)