import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.model_assignment import ModelAssignment  # noqa: F401 (registers in metadata)
from src.models.model_preference import ModelPreference

router = APIRouter(prefix="/api/settings", tags=["settings"])
assignments_router = APIRouter(prefix="/api/model-assignments", tags=["model-assignments"])


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


@assignments_router.get("")
def get_model_assignments(user=Depends(current_user), db: Session = Depends(get_db)):
    from src.models.model_assignment import ModelAssignment
    rows = db.query(ModelAssignment).filter_by(user_id=user.id).all()
    return {"assignments": {r.task: r.model_id for r in rows}}


@assignments_router.put("")
def put_model_assignments(body: dict, user=Depends(current_user), db: Session = Depends(get_db)):
    from fastapi import HTTPException

    from src.models.model_assignment import ModelAssignment
    from src.services.llm_service import ASSIGNMENT_TASKS

    assignments = body.get("assignments") or {}
    bad = [t for t in assignments if t not in ASSIGNMENT_TASKS]
    if bad:
        raise HTTPException(status_code=400, detail=f"unknown tasks: {bad}")
    for task, model_id in assignments.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise HTTPException(status_code=400, detail=f"invalid model_id for {task}")
        row = db.query(ModelAssignment).filter_by(user_id=user.id, task=task).first()
        if row:
            row.model_id = model_id.strip()
        else:
            session_row = ModelAssignment(user_id=user.id, task=task,
                                          model_id=model_id.strip())
            db.add(session_row)
    db.commit()
    return {"ok": True}
