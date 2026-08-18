# Phase 7: FastAPI Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Flask backend to **FastAPI + Pydantic v2**, keeping the same API surface (`/api/*`), same DB (SQLite, same tables via Alembic), same Celery pipeline, and the same frontend — no frontend changes required. Migration is incremental: run FastAPI app on port 5004 (or 5005 with proxy change), reusing services untouched.

**Architecture:** New `fastapi_app/` package co-existing with old `src/` during transition. Phase runs in steps so the app stays functional: (1) FastAPI scaffold + health + auth, (2) users/projects/tasks/presets/api-keys/models/templates routes, (3) generation + voices + uploads + static media, (4) Alembic schema mirror, (5) Celery integration, (6) swap default entrypoint + delete old app after green tests. Reuse all of `src/services/` (llm, celery, storage, tts_client, video assembly) and `src/models/` + `src/database.py` as-is — only the HTTP layer changes.

**Tech Stack:** fastapi 0.116.1 (ALREADY pinned in requirements.txt:19, NOT installed in venv yet), uvicorn 0.35.0, pydantic v2, PyJWT 2.10.1, SQLAlchemy 2.0.41 + Flask-SQLAlchemy (KEEP — do NOT migrate models to SQLModel), Alembic 1.15.1, Celery 5.5.3 (unchanged). python-multipart 0.0.20 + email-validator 2.3.0 already pinned (needed for UploadFile/EmailStr).

## ⚠️ Reality-check corrections (prep agents, Aug 2026) — READ FIRST

These correct the original plan draft. Where they conflict with the text below, the corrections win.

1. **fastapi version**: plan said "0.136 (already in requirements)". Reality: `requirements.txt:19` pins `fastapi==0.116.1` and fastapi/uvicorn/starlette/sqlmodel/alembic/python-multipart/email-validator are NOT installed in the venv. Fix: `source venv/bin/activate && python -m pip install -r requirements.txt` then `python -m pip install sqlmodel alembic`. (sqlmodel installs even though models stay Flask-SQLAlchemy — keep it out of app imports if unused, or drop the pin.)
2. **venv**: `venv312` is DEAD (dangling python3.12 symlink). All `source venv312/bin/activate` (old lines 134, 219) → `source venv/bin/activate`. `venv/bin/pip` is also broken (stale absolute shebang) → always `python -m pip`.
3. **BIGGEST GAP — SQLModel cannot query Flask-SQLAlchemy models.** `src/models/*` are Flask-SQLAlchemy declarative (`get_db().Model` pattern, `database.py:1-4`); they need a Flask app context for `db.session`/`X.query`. The draft's `sqlmodel.Session` + `session.exec(select(User))` (Task 1 Step 4) WILL NOT WORK. **Decision: keep Flask-SQLAlchemy.** Create `fastapi_app/db.py` that instantiates a bare `Flask(__name__)`, sets `SQLALCHEMY_DATABASE_URI` from `DATABASE_URL`, calls `db.init_app(app)`, and exposes a FastAPI `get_db()` dependency that yields `db.session` inside `with flask_app.app_context():`. All route handlers that touch models run synchronously (`def`, not `async def`) and use `db.session` / `Model.query` exactly as today. Alembic `target_metadata = db.metadata`.
4. **Blocklist check missing from draft deps**: FastAPI `current_user` MUST check `TokenBlocklist` (src/auth.py:40-41) — logout + DELETE /users/me insert jti rows; tests pin that revoked tokens get 401 (test_auth.py:30-32, test_user_routes:214-221).
5. **Response schemas**: `MeResponse {id,username,email}` in draft drops `created_at`/`updated_at`. `user.to_dict()` returns all 5 fields and the frontend/tests read them. Either add all 5 fields or skip `response_model` for user responses (prefer the latter — plain dicts match Flask exactly). `EmailStr` needs email-validator (pinned). Register duplicate → **400** (auth.py:23-27), NOT 409.
6. **Upload handling split** (draft Task 3 Step 2 wrong): `/clone-voice` = multipart (`UploadFile` + `Form` text, voice_cloning.py:22-35); `/voices` POST = JSON `{name, consent, reference_audio_url}` (voices.py:112-172); `/uploads/<key>` PUT = **raw body** via `await request.body()` (or `Request.stream`), 25MB cap (upload.py:13,38-44), NOT UploadFile.
7. **Celery call signature** (draft Task 5 wrong): tasks are `bind=True` with signature `generate_assembler_video_task(project_id, prompt, duration=30, orientation="landscape", width=1920, height=1080, voice_id=None)` (video_tasks.py:125-126). Routes call `.delay(project.id, prompt, duration=..., orientation=..., width=..., height=..., voice_id=...)`. Queue is already routed via `task_routes` (celery_app.py:19-21). **KEEP `.delay(...)` with identical args** — tests `mock.patch.object(..., 'delay')` and assert kwargs (test_tasks.py:66,98,114; test_video_generation_routes.py:68,109,123). Do NOT use `apply_async(args=[task.id])`. Wire ALL FOUR tasks (assembler, generative, batch_mix, clone_voice).
8. **Worker queues**: `--queues=video_generation` alone breaks default-queue tasks. Use `celery -A src.tasks.video_tasks worker --concurrency=2 --queues=celery,video_generation` (matches start_all_services.sh:51).
9. **Missing routers in task list**: draft Tasks 2/3 omit `/api/api-keys/*` + `/api/models*` (api_keys.py:18-221, 5 routes + 2 model routes) and `/api/templates*` (templates.py:9-88) and `/api/batch-mix` + `/api/task-status/{id}` (video_generation.py:187-361). All MUST be ported — frontend reads api-keys/models/templates (SettingsPage).
10. **Static media routes missing from every task**: `/final/{filename}` + `/media/{filename}` (main.py:139-199) with Bearer-or-`?token=` auth, `Accept-Ranges: bytes` (Starlette FileResponse is Range-aware), plain-text 401/404. Frontend REQUIRES both (`?token=` appending, api.js:9-16, resolveMediaUrl). Add to Task 1.
11. **Error shape**: FastAPI defaults to `{detail}` + 422 for validation. ALL tests and frontend expect `{error}` (api.js:57-58 throws `errorData.error`) and 400 for bad bodies (test_project.py:36-41, test_voices:37-40, test_auth:53-56). Add exception handlers: `HTTPException` → `{error: detail}`, `RequestValidationError` → **400** `{error: "..."}` (first error msg). Task 1 delivers these.
12. **Preset seeding**: currently inline in `src/main.py:88-101` (no function, seeds 6 presets at import). FastAPI needs lifespan/startup seeding of the SAME 6 rows or test_presets fails. Port into FastAPI lifespan. Keep the shared `_SEED_PRESETS`/seed function visible for tests.
13. **conftest.py:28 `from src.main import app, db` breaks when main.py is deleted** (Task 6). Rewrite conftest app fixture to build FastAPI TestClient; legacy unittest files (test_user_routes.py, test_video_generation_routes.py) import blueprints + patch `src.routes.*` symbols — those two files must be rewritten/deleted in Task 6 (they test the retired Flask layer). test_video_tasks_voice.py uses `create_app_context()` and survives. Monkeypatch targets must keep identical names in FastAPI routers: `src.routes.voices.validate_audio`, `get_storage`, `requests.post`, `FINAL_DIR`, `MAX_FILE_BYTES`; `generate_assembler_video_task.delay`.
14. **`/api/health` contract flip**: today it's the Flask SPA catch-all → 200 text/html (test_auth_smoke.py:9-16). Plan makes it JSON. Frontend never calls it (grep clean) so this is the ONE intentional contract deviation — rewrite test_auth_smoke in Task 1. Keep SPA catch-all for `/` + `/{path}` (StaticFiles html=True or FileResponse index).
15. **Alembic metadata**: `target_metadata` must be `db.metadata` (Flask-SQLAlchemy) with ALL 9 models imported (main.py:66-75 imports only 8 — token_blocklist/template/voice missing there; import every model module). Verify `.schema` matches existing app.db.
16. **task.result is a JSON string**, not a dict (task.py:16,113-125,171-186). Pydantic must type it `str`, and the status/list routes keep `json.loads`→resolve-media→`json.dumps` behavior exactly.
17. **Coverage config**: pytest.ini `--cov=src` won't see `fastapi_app/`; deleting `src/routes` shrinks covered lines. Task 6 must update pytest.ini (add `--cov=fastapi_app` or re-baseline floor). Keep floor ≥ actual measured (recompute after Task 6).
18. **Sync routes**: all services (storage, Celery, requests, litellm, subprocess/ffprobe) are blocking → use `def` endpoints (FastAPI threadpool), only raw-body PUT / multipart reads need `async def`. CORS middleware allow_methods must include PUT (upload proxy). No cookies → no allow_credentials.
19. **start_all_services.sh**: still uses venv312 (broken) and runs Flask `python src/main.py` (port 5004). Task 6 must switch to `venv` + `python run.py`. Until Task 6, Flask stays the running app (rollback path).
20. **DATABASE_URL single source**: draft hardcoded absolute sqlite path in db.py — keep `DATABASE_URL` env default matching current (main.py:62 default), read once, no duplicated paths. Path contains spaces — use `sqlite:///{abspath}` form, works.

## Global Constraints

- API contract identical to Flask version (same routes, same JSON shapes, `{error}` errors) — frontend untouched
- All Phase 1 auth behavior preserved: JWT Bearer, owner-scoping, token blocklist
- Phase 6 test suite must pass against FastAPI app (pytest httpx TestClient) — after Task 6 conversion
- Models stay Flask-SQLAlchemy (`src/models/*`, `src/database.py`) — NOT rewritten
- Services package (`src/services/*`) NOT rewritten in this phase — reuse as-is
- SQLite schema identical; Alembic generates migration against existing `app.db` (autogenerate as baseline, `db.metadata`)
- Frontend still calls `http://localhost:5004/api` — FastAPI must bind same port in dev (Task 5 run.py)
- Keep old Flask app runnable until final task (rollback path)

---

### Task 1: FastAPI scaffold + shared services wiring

**Files:**
- Create: `fastapi_app/__init__.py`
- Create: `fastapi_app/main.py`
- Create: `fastapi_app/db.py`
- Create: `fastapi_app/deps.py` (auth dependency)
- Create: `fastapi_app/schemas/__init__.py`
- Create: `fastapi_app/errors.py` (exception handlers → `{error}`)
- Create: `fastapi_app/routers/__init__.py`, `routers/health.py`, `routers/auth.py`, `routers/media.py`
- Modify: `requirements.txt` (sqlmodel, alembic) — fastapi/uvicorn/multipart/email-validator already pinned
- Modify: `tests/test_auth_smoke.py` (health now JSON)

**Interfaces:**
- Produces: FastAPI app with `/api/health` (JSON), `/api/auth/login`, `/api/auth/register`, `/api/auth/logout`, `/api/auth/me` working against SQLite (Flask-SQLAlchemy models), `/final/` + `/media/` static serving, SPA catch-all `/`, `{error}` exception handlers.

- [ ] **Step 1: Install deps**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install sqlmodel alembic
```

- [ ] **Step 2: db.py** — keep Flask-SQLAlchemy:

```python
from flask import Flask
from src.database import db  # unbound SQLAlchemy() instance

flask_app = Flask(__name__)
import os
flask_app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:///' + os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'database', 'app.db')))
flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(flask_app)

def get_db():
    with flask_app.app_context():
        yield db.session
```

- [ ] **Step 3: errors.py** — `{error}` shape, 400 for validation:

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError

def register_error_handlers(app: FastAPI):
    @app.exception_handler(HTTPException)
    async def http_exc(request, exc):
        return JSONResponse(status_code=exc.status_code, content={'error': exc.detail})
    @app.exception_handler(RequestValidationError)
    async def val_exc(request, exc):
        first = exc.errors()[0]
        msg = first['msg'] if first['loc'] == ('body',) else f"{first['loc'][-1]}: {first['msg']}"
        return JSONResponse(status_code=400, content={'error': msg})
```

- [ ] **Step 4: schemas** (Pydantic v2; user responses as plain dicts — skip response_model for them)

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
```

- [ ] **Step 5: deps.py (auth)** — mirror Flask exactly, WITH blocklist:

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt, os
from src.models.user import User
from src.models.token_blocklist import TokenBlocklist

bearer = HTTPBearer(auto_error=False)

def current_user(creds: HTTPAuthorizationCredentials = Depends(bearer),
                 session=Depends(get_db)):
    if creds is None:
        raise HTTPException(401, 'Missing token')
    try:
        payload = jwt.decode(creds.credentials, os.environ['SECRET_KEY'], algorithms=['HS256'])
    except Exception:
        raise HTTPException(401, 'Invalid token')
    if session.query(TokenBlocklist).filter_by(jti=payload['jti']).first():
        raise HTTPException(401, 'Token revoked')
    user = session.get(User, payload['user_id'])
    if user is None:
        raise HTTPException(401, 'User not found')
    return user
```

- [ ] **Step 6: main.py + routers** — CORS (allow PUT), include routers, lifespan preset seeding (port the 6 `_SEED_PRESETS` rows from main.py:88-101), SPA catch-all, `media.py` static `/final/` + `/media/` with Bearer-or-`?token=` + FileResponse (Range-aware) + plain-text 401/404. Auth handlers (register/login/logout/me) ported 1:1 from `src/routes/auth.py` (register dup → 400, login 200/401, logout inserts blocklist then `{message:"Logged out"}`, me returns `user.to_dict()`). Sync `def` handlers.
- [ ] **Step 7: Verify + commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv/bin/activate
python -m uvicorn fastapi_app.main:app --port 5005 &
curl -s http://localhost:5005/api/health      # {"status":"ok"}
# register/login/me/logout smoke
```
Update `tests/test_auth_smoke.py` to assert JSON health on the FastAPI app (contract flip — the one intentional deviation).

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat(fastapi): scaffold app, health, auth routes, error handlers"
```

---

### Task 2: Users / Projects / Tasks / Presets / Api-keys / Models / Templates routers

**Files:**
- Create: `fastapi_app/routers/users.py`, `projects.py`, `tasks.py`, `presets.py`, `api_keys.py`, `templates.py`
- Modify: `fastapi_app/main.py` (include routers)

**Interfaces:**
- Produces: CRUD for users/me, projects, tasks, presets, api-keys, models, templates with same JSON as Flask

- [ ] **Step 1: Port routes**

Copy handler logic from `src/routes/{user,project,task,presets,api_keys,templates}.py`, replacing `@app.route` with FastAPI `@router.get/post/patch/delete`, `request.get_json()` → Pydantic body models, `g.current_user` → `current_user` dep. Keep owner-scoping queries identical (`_user_has_child_data`, `_resolve_owned_voice` equivalents with same names for monkeypatch compatibility). User responses = `user.to_dict()` plain dicts. DELETE /users/me → 409 `{error}` when owns projects/keys (user.py:71-79), inserts blocklist then deletes (user.py:80-88). `/users/{id}` → 403 for non-self. api-keys: GET `/user/{id}` → 403 if not self (api_keys.py), POST/DELETE/test shapes exact (`{success:false,error}` 400 for test). `/models` always 200 even on proxy failure (api_keys.py:196-212). `/models/default` → `{default_model:"groq/llama-3.1-70b-versatile"}`. templates: own+public scoping (templates.py:9-88).

- [ ] **Step 2: Port validation**

Use existing `src/validation.py` helpers or Pydantic constraints; bad body → 400 `{error}` via RequestValidationError handler. `data='null'` body → 400.

- [ ] **Step 3: Verify + commit**

Smoke against port 5005: create project, list, get, update, delete with token; api-keys CRUD; models; templates; users/me PATCH/DELETE (409 path).

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat(fastapi): users, projects, tasks, presets, api-keys, models, templates routers"
```

---

### Task 3: Generation / Voices / Uploads routers + static media

**Files:**
- Create: `fastapi_app/routers/generation.py`, `voices.py`, `uploads.py`
- Modify: `fastapi_app/main.py`

**Interfaces:**
- Produces: `/api/generate/*`, `/api/batch-mix`, `/api/task-status/{id}`, `/api/clone-voice`, `/api/voices`, `/api/uploads/presign`, `/api/uploads/{key}` (raw PUT) on FastAPI

- [ ] **Step 1: Port generation + clone-voice**

Reuse `src/tasks/video_tasks.py` + `src/services/tts_client.py` + `src/services/video/*` unchanged. Call `.delay(project_id=..., prompt=..., duration=..., orientation=..., width=..., height=..., voice_id=...)` with the EXACT per-task signatures (4 tasks: assembler, generative, batch_mix, clone_voice). 202 responses `{message, task_id, celery_task_id, project_id}` (+ `settings` for assembler, `variations_count` for batch-mix). Owner + voice-owner 403s. `/task-status/{celery_task_id}` → `{state,current,total,status[,result]}` 404/403. clone-voice = `UploadFile` + `Form` text → 202.

- [ ] **Step 2: Port voices + uploads**

`/voices` GET/POST/DELETE/preview — POST JSON `{name, consent, reference_audio_url, description?}` (NOT multipart), `validate_audio`/`get_storage`/`requests.post`/`FINAL_DIR`/`MAX_FILE_BYTES` monkeypatch-compatible names, preview → `{preview_url:"/final/<name>"}` (404/403/410/503/502). `/uploads/presign?ext=` → `{upload_url, object_key}`. `/uploads/{key}` = **raw-body PUT** (`await request.body()`, 25MB cap → 413), validates `is_valid_storage_key` + ownership, returns `{ok, object_key}`.

- [ ] **Step 3: Verify + commit**

Full flow smoke: create voice (presign→PUT→POST), generate assembler video (mock .delay), poll status, preview.

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat(fastapi): generation, voices, uploads, clone-voice routers"
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
source venv/bin/activate
python -m alembic init migrations
```

- [ ] **Step 2: Configure env.py**

Set `sqlalchemy.url` from `DATABASE_URL`; `target_metadata = db.metadata` (Flask-SQLAlchemy) — import ALL 9 model modules (user, project, task, media_asset, api_key, format_presets, video_templates, voices, token_blocklist) so autogenerate sees every table.

- [ ] **Step 3: Autogenerate baseline**

```bash
python -m alembic revision --autogenerate -m "baseline schema"
python -m alembic upgrade head
```

Verify against copy of existing app.db: `sqlite3 src/database/app.db '.schema'` matches migration-created schema (table names + columns). No data loss on a copy.

- [ ] **Step 4: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat(fastapi): alembic baseline migration"
```

---

### Task 5: Celery integration + port swap

**Files:**
- Modify: `fastapi_app/routers/generation.py` (Celery `.delay(...)` wired — from Task 3)
- Create: `run.py` (uvicorn entrypoint on 5004)

**Interfaces:**
- Produces: Celery workers consume tasks enqueued from FastAPI; app serves on 5004

- [ ] **Step 1: Reuse Celery**

```python
from src.services.celery_app import celery_app  # broker/result REDIS_URL, task_routes already set
```

Generation routes keep calling the task functions' `.delay(project_id=..., prompt=..., ...)` with exact signatures — queue routing is automatic via `task_routes` (celery_app.py:19-21). No `apply_async` needed.

- [ ] **Step 2: run.py**

```python
import uvicorn, os
if __name__ == '__main__':
    uvicorn.run('fastapi_app.main:app', host='0.0.0.0', port=int(os.getenv('PORT', '5004')))
```

- [ ] **Step 3: Verify + commit**

Stop Flask app; start `python run.py`; start worker (`celery -A src.tasks.video_tasks worker --concurrency=2 --queues=celery,video_generation`). Enqueue a task (mock or live if services available), confirm broker accept. Full E2E against FastAPI on 5004.

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat(fastapi): celery integration, run.py on port 5004"
```

---

### Task 6: Phase 6 test suite against FastAPI + retire Flask

**Files:**
- Modify: `money_weaver_backend/tests/conftest.py` (build FastAPI TestClient)
- Modify: `money_weaver_backend/tests/test_auth_smoke.py` (already JSON in T1)
- Rewrite/Delete: `tests/test_user_routes.py`, `tests/test_video_generation_routes.py` (import Flask blueprints — retire with Flask layer; delete or convert to FastAPI equivalents)
- Modify: `pytest.ini` (`--cov` add `fastapi_app` or re-baseline floor)
- Delete (after green): old Flask app entry + `src/routes/*` + `src/main.py` (keep `src/database.py`, `src/models/`, `src/services/`, `src/tasks/`, `src/auth.py`)
- Modify: `start_all_services.sh` (venv + `python run.py`, not venv312 + Flask)

**Interfaces:**
- Produces: `pytest` green against FastAPI; Flask HTTP layer removed

- [ ] **Step 1: TestClient for FastAPI**

In conftest, build app from `fastapi_app.main:app` + `TestClient` (httpx). Update `app`/`client`/`auth_headers` fixtures (same endpoints). Ensure env (SECRET_KEY, DATABASE_URL→temp sqlite, STORAGE_*) set at module top BEFORE importing fastapi_app.main (it imports src models/services). Re-seed presets after drop_all (startup seed + test reseed). `r.get_json()` → `.json()` everywhere in new pytest files.

- [ ] **Step 2: Run suite**

```bash
source venv/bin/activate
python -m pytest
```

All pass against FastAPI. Re-baseline `--cov-fail-under` to measured total (add `--cov=fastapi_app` or adjust floor). Fix any shape drift surfaced by tests (this is the contract gate).

- [ ] **Step 3: Delete old Flask HTTP layer**

Remove `src/routes/` + `src/main.py` Flask app + their two legacy unittest files. Keep `src/database.py`, `src/models/`, `src/services/`, `src/tasks/`, `src/auth.py`. Update `start_all_services.sh` (venv, `python run.py`). Verify nothing else imports `src.main`/`src.routes` (grep).

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

Update root README: FastAPI + uvicorn startup (`python run.py`), alembic migration step, venv note. Confirm test commands still documented correctly (backend pytest count now reflects FastAPI suite).

- [ ] **Step 2: Final full-stack smoke**

Everything green (backend tests, frontend tests, manual E2E on 5004).

- [ ] **Step 3: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: phase 7 fastapi migration verified"
```