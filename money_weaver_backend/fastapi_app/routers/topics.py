from fastapi import APIRouter, Depends, Query

from fastapi_app.deps import current_user
from src.services.topic_service import fetch_topics

router = APIRouter(prefix="/api", tags=["topics"])


@router.get("/topics")
def get_topics(niche: str = Query("general"), limit: int = Query(20, le=50),
               user=Depends(current_user)):
    return {"topics": fetch_topics(niche, limit)}