import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.model_preference import ModelPreference

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/models")
def get_model_prefs(user=Depends(current_user), db: Session = Depends(get_db)):
    prefs = db.query(ModelPreference).filter_by(user_id=user.id).first()
    if not prefs:
        return {"defaults": {}, "fallbacks": []}
    d = prefs.to_dict()
    return {"defaults": d.get("defaults", {}), "fallbacks": d.get("fallbacks", [])}


@router.put("/models")
def put_model_prefs(body: dict, user=Depends(current_user), db: Session = Depends(get_db)):
    prefs = db.query(ModelPreference).filter_by(user_id=user.id).first()
    if not prefs:
        prefs = ModelPreference(user_id=user.id)
        db.add(prefs)
    prefs.defaults = json.dumps(body.get("defaults", {}))
    prefs.fallbacks = json.dumps(body.get("fallbacks", []))
    db.commit()
    d = prefs.to_dict()
    return {"defaults": d.get("defaults", {}), "fallbacks": d.get("fallbacks", [])}
