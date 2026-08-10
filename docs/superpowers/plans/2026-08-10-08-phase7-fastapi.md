# Phase 7: FastAPI Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Flask backend to **FastAPI 0.136 + SQLModel + Pydantic v2**, keeping the same API surface (`/api/*`), same DB (SQLite, same tables via Alembic), same Celery pipeline, and the same frontend — no frontend changes required. Migration is incremental: run FastAPI app on port 5004 (or 5005 with proxy change), reusing services untouched.

**Architecture:** New `fastapi_app/` package co-existing with old `src/` during transition. Phase runs in steps so the app stays functional: (1) FastAPI scaffold + health + auth, (2) users/projects/tasks routes, (3) generation + voices + presets + uploads, (4) Alembic schema mirror, (5) Celery integration, (6) swap default entrypoint + delete old app after green tests. Reuse all of `src/services/` (llm, celery, storage, tts_client, video assembly) as-is — only the HTTP layer changes.

**Tech Stack:** fastapi 0.136 (already in requirements), uvicorn, pydantic v2, SQLModel, Alembic, python-jose or PyJWT (keep PyJWT), Celery (unchanged).

## Global Constraints

- API contract identical to Flask version (same routes, same JSON shapes) — frontend untouched
- All Phase 1 auth behavior preserved: JWT Bearer, owner-scoping, token blocklist
- Phase 6 test suite must pass against FastAPI app (pytest httpx TestClient)
- Services package (`src/services/*`) NOT rewritten in this phase — reuse as-is
- SQLite schema identical; Alembic generates migration against existing `app.db` (autogenerate as baseline)
- Frontend still calls `http://localhost:5004/api` — FastAPI must bind same port in dev
- Keep old Flask app runnable until final task (rollback path)

---

### Task 1: FastAPI scaffold + shared services wiring

**Files:**
- Create: `fastapi_app/__init__.py`
- Create: `fastapi_app/main.py`
- Create: `fastapi_app/db.py`
- Create: `fastapi_app/deps.py` (auth dependency)
- Create: `fastapi_app/schemas/__init__.py`
- Modify: `requirements.txt` (sqlmodel, alembic)

**Interfaces:**
- Produces: FastAPI app with `/api/health`, `/api/auth/login`, `/api/auth/register` working against SQLite

- [ ] **Step 1: Add deps**

```
sqlmodel==0.0.26
alembic==1.15.1
```

Install: `pip install sqlmodel alembic`

- [ ] **Step 2: db.py**

```python
from sqlmodel import SQLModel, create_engine, Session
import os

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:////Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend/src/database/app.db')
connect_args = {'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

def get_session():
    with Session(engine) as s:
        yield s
```

- [ ] **Step 3: schemas**

```python
# schemas/auth.py
from pydantic import BaseModel, EmailStr

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str

class TokenResponse(BaseModel):
    token: str
    user: dict

class MeResponse(BaseModel):
    id: int
    username: str
    email: str
```

- [ ] **Step 4: deps.py (auth)**

```python
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt, os
from sqlmodel import Session, select
from src.models.user import User  # reuse existing model table

bearer = HTTPBearer(auto_error=False)

def current_user(request: Request, creds: HTTPAuthorizationCredentials = Depends(bearer),
                 session: Session = Depends(get_session)):
    if creds is None:
        raise HTTPException(401, 'Missing token')
    try:
        payload = jwt.decode(creds.credentials, os.environ['SECRET_KEY'], algorithms=['HS256'])
    except Exception:
        raise HTTPException(401, 'Invalid token')
    user = session.exec(select(User).where(User.id == payload['user_id'])).first()
    if user is None:
        raise HTTPException(401, 'User not found')
    request.state.user = user
    return user
```

Note: keep `src.models` (SQLAlchemy models) — SQLModel is a superset and can query the same tables. Import `db` engine config from old `src.database` for consistency. Simplify by keeping SQLAlchemy models and using SQLModel only for new Pydantic-validated routes; OR duplicate model defs in SQLModel. Choose: **reuse old models via `src.models.*`** (they're SQLAlchemy) + FastAPI dependency injection. Alembic autogenerate uses `src.models` metadata.

- [ ] **Step 5: main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title='MoneyWeaver API')
app.add_middleware(CORSMiddleware, allow_origins=[os.getenv('FRONTEND_ORIGIN', 'http://localhost:5173')], allow_methods=['*'], allow_headers=['*'])

from fastapi_app.routers import auth, health
app.include_router(health.router)
app.include_router(auth.router, prefix='/api/auth')
```

Create `routers/health.py`, `routers/auth.py` with the same handlers as Flask `src/routes/auth.py` (register/login/logout/me), using `current_user` dep.

- [ ] **Step 6: Verify + commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv312/bin/activate
uvicorn fastapi_app.main:app --port 5005 &
curl -s http://localhost:5005/api/health
# register/login/me
```

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat(fastapi): scaffold app, health and auth routes"
```

---

### Task 2: Users / Projects / Tasks routes

**Files:**
- Create: `fastapi_app/routers/users.py`, `projects.py`, `tasks.py`, `presets.py`
- Modify: `fastapi_app/main.py` (include routers)

**Interfaces:**
- Produces: CRUD for users/me, projects, tasks, presets with same JSON as Flask

- [ ] **Step 1: Port routes**

Copy handler logic from `src/routes/{user,project,task,presets}.py`, replacing `@app.route` with FastAPI `@router.get/post/patch/delete`, `request.get_json()` → Pydantic body models, `g.current_user` → `current_user` dep. Keep owner-scoping queries identical.

- [ ] **Step 2: Port validation**

Use existing `src/validation.py` helpers or Pydantic constraints.

- [ ] **Step 3: Verify + commit**

Run smoke against port 5005: create project, list, get, update, delete with token.

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat(fastapi): users, projects, tasks, presets routers"
```

---

### Task 3: Generation / Voices / Uploads routers

**Files:**
- Create: `fastapi_app/routers/generation.py`, `voices.py`, `uploads.py`
- Modify: `fastapi_app/main.py`

**Interfaces:**
- Produces: `/api/generate/*`, `/api/clone-voice`, `/api/voices`, `/api/uploads/presign` on FastAPI

- [ ] **Step 1: Port generation + clone-voice**

Reuse `src/tasks/video_tasks.py` + `src/services/tts_client.py` + `src/services/video/*` unchanged. Same request/response shapes. File upload via `UploadFile`.

- [ ] **Step 2: Port voices + uploads**

`UploadFile` handling for reference audio; call presign + TTS client same as Flask.

- [ ] **Step 3: Verify + commit**

Full flow: create voice, generate video, poll status — against FastAPI.

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat(fastapi): generation, voices, uploads routers"
```

---

### Task 4: Alembic schema baseline

**Files:**
- Create: `alembic.ini`, `migrations/`
- Modify: none in app code

**Interfaces:**
- Produces: `alembic upgrade head` creates identical schema; no data loss on existing app.db

- [ ] **Step 1: Init alembic**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv312/bin/activate
alembic init migrations
```

- [ ] **Step 2: Configure env.py**

Point `sqlalchemy.url` at `DATABASE_URL`; set `target_metadata` to merged metadata from `src.models` (import all models). 

- [ ] **Step 3: Autogenerate baseline**

```bash
alembic revision --autogenerate -m "baseline schema"
alembic upgrade head
```

Verify against copy of existing app.db: `sqlite3 src/database/app.db '.schema'` matches.

- [ ] **Step 4: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat(fastapi): alembic baseline migration"
```

---

### Task 5: Celery integration + port swap

**Files:**
- Modify: `fastapi_app/deps.py` or a worker config reusing `src/services/celery_app.py`
- Modify: `fastapi_app/routers/generation.py` (use Celery apply_async)
- Create: `run.py` (uvicorn entrypoint on 5004)

**Interfaces:**
- Produces: Celery workers consume tasks enqueued from FastAPI; app serves on 5004

- [ ] **Step 1: Reuse Celery**

```python
from src.services.celery_app import celery_app
celery_app.conf.update(task_serializer='json', result_serializer='json', accept_content=['json'])
```

Generation routes: `generate_assembler_video_task.apply_async(args=[task.id], queue='video_generation')`.

- [ ] **Step 2: run.py**

```python
import uvicorn
if __name__ == '__main__':
    uvicorn.run('fastapi_app.main:app', host='0.0.0.0', port=int(os.getenv('PORT', '5004')))
```

- [ ] **Step 3: Verify + commit**

Stop Flask app; start `python run.py`; start worker (`celery -A src.tasks.video_tasks worker --concurrency=2 -Q video_generation`). Full E2E.

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat(fastapi): celery integration, run.py on port 5004"
```

---

### Task 6: Phase 6 test suite against FastAPI + retire Flask

**Files:**
- Modify: `money_weaver_backend/tests/conftest.py` (point at FastAPI app)
- Delete (after green): old Flask app entry + `src/routes/*` (keep `src/services/*`, `src/tasks/*`, `src/models/*`)

**Interfaces:**
- Produces: `pytest` green against FastAPI; Flask routes removed

- [ ] **Step 1: TestClient for FastAPI**

In conftest, build TestClient from `fastapi_app.main:app` with `TestClient` (httpx). Update auth_headers fixture (same endpoints). Fix any shape drift.

- [ ] **Step 2: Run suite**

```bash
pytest
```

All pass against FastAPI.

- [ ] **Step 3: Delete old Flask HTTP layer**

Remove `src/routes/` + `src/main.py` Flask app (or keep as `legacy/`), update `README` entrypoints. Keep `src/database.py`, `src/models/`, `src/services/`, `src/tasks/`, `src/auth.py` (used by FastAPI deps or removed if duplicated).

- [ ] **Step 4: Full verify**

```bash
python run.py &   # FastAPI on 5004
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_frontend && pnpm dev
# manual: register, dashboard, create video, play
```

- [ ] **Step 5: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "refactor: swap Flask for FastAPI, retire old HTTP layer"
```

---

### Task 7: Phase 7 verification

- [ ] **Step 1: Docs + README update**

Update root README: FastAPI + uvicorn startup command, `run.py`, alembic migration step.

- [ ] **Step 2: Final full-stack smoke**

Everything green (backend tests, frontend tests, manual E2E).

- [ ] **Step 3: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: phase 7 fastapi migration verified"
```
