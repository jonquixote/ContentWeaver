from fastapi import APIRouter, Depends

from fastapi_app.deps import current_user
from src.services.providers.niche_profile import list_niches

router = APIRouter(prefix="/api", tags=["niches"])


@router.get("/niches")
def get_niches(user=Depends(current_user)):
    return {"niches": list_niches()}
