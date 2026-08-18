import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from fastapi_app.db import db_session, engine
from fastapi_app.errors import register_error_handlers
from fastapi_app.routers import (
    api_keys,
    auth,
    health,
    media,
    presets,
    projects,
    tasks,
    templates,
    users,
)
from src.database import db

# SECRET_KEY is required, mirroring src/main.py.
_ = os.environ['SECRET_KEY']

SEED_PRESETS = [
    ('YouTube Landscape', 'youtube', 1920, 1080, 30, 60, 600, True),
    ('YouTube Shorts', 'shorts', 1080, 1920, 30, 15, 60, False),
    ('TikTok', 'tiktok', 1080, 1920, 30, 15, 60, False),
    ('Instagram Reels', 'reels', 1080, 1920, 30, 15, 60, False),
    ('Instagram Square', 'instagram', 1080, 1080, 30, 15, 60, False),
    ('Twitter/X', 'twitter', 1280, 720, 30, 15, 60, False),
]

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'static')


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.models.api_key import ApiKey
    from src.models.media_asset import MediaAsset
    from src.models.preset import FormatPreset
    from src.models.project import Project
    from src.models.task import Task
    from src.models.template import VideoTemplate
    from src.models.user import User
    from src.models.voice import Voice

    db_url = os.getenv('DATABASE_URL', '')
    if db_url.startswith('sqlite:///'):
        db_dir = os.path.dirname(db_url[len('sqlite:///'):])
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    db.metadata.create_all(bind=engine)

    # Lightweight migrations for columns added after initial creation (mirrors src/main.py).
    from sqlalchemy import inspect as _inspect, text as _text
    _cols = [c['name'] for c in _inspect(engine).get_columns('task')]
    if 'thumbnail_path' not in _cols:
        with engine.connect() as _conn:
            _conn.execute(_text("ALTER TABLE task ADD COLUMN thumbnail_path VARCHAR(500)"))
            _conn.commit()

    # Seed default format presets (mirrors src/main.py:88-101).
    with db_session() as session:
        if session.query(FormatPreset).count() == 0:
            for name, platform, w, h, fps, dmin, dmax, is_def in SEED_PRESETS:
                session.add(FormatPreset(name=name, platform=platform, width=w, height=h,
                                         fps=fps, duration_min=dmin, duration_max=dmax,
                                         is_default=is_def))
            session.commit()
    yield


app = FastAPI(title='MoneyWeaver API', lifespan=lifespan)

register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173')],
    allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allow_headers=['*'],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(media.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(presets.router)
app.include_router(api_keys.router)
app.include_router(api_keys.models_router)
app.include_router(templates.router)


@app.get('/', include_in_schema=False)
def serve_index():
    return _serve_static('')


@app.get('/{path:path}', include_in_schema=False)
def serve_spa(path: str):
    return _serve_static(path)


def _serve_static(path):
    full = os.path.join(STATIC_DIR, path)
    if path and os.path.isfile(full):
        return FileResponse(full)
    index_path = os.path.join(STATIC_DIR, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return PlainTextResponse('index.html not found', 404)