from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.model_preference import ModelPreference
from src.services.llm_service import llm_service

router = APIRouter(prefix='/api/ideas', tags=['ideas'])


@router.post('/random')
def random_idea(body: dict, user=Depends(current_user), db: Session = Depends(get_db)):
    prefs = db.query(ModelPreference).filter_by(user_id=user.id).first()
    prefs_dict = prefs.to_dict() if prefs else None
    model = body.get('model') or llm_service.pick_model(user.id, prefs_dict, 'idea')
    try:
        return llm_service.generate_idea(seed=body.get('seed'), model=model,
                                         language=body.get('language', 'en'),
                                         user_id=user.id)
    except Exception as e:
        raise HTTPException(503, f'Idea generation unavailable: {e}')
