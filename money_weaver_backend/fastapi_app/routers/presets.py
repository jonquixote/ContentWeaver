from fastapi import APIRouter, Depends

from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.preset import FormatPreset

router = APIRouter(prefix='/api/presets', tags=['presets'])


@router.get('')
def list_presets(user=Depends(current_user), session=Depends(get_db)):
    presets = session.query(FormatPreset).order_by(
        FormatPreset.is_default.desc(), FormatPreset.name).all()
    return [p.to_dict() for p in presets]