from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix='/api', tags=['health'])


@router.get('/health')
def health():
    return JSONResponse({'status': 'ok'})