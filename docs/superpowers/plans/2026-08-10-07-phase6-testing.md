# Phase 6: Testing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a real test suite (pytest backend, Vitest frontend) that covers the critical paths introduced in Phases 0-5, so Phase 7 (FastAPI migration) has a safety net. Target: auth, owner-scoping (IDOR), presets, tasks, voices, storage abstraction, frontend hooks.

**Architecture:** Backend: pytest + pytest-asyncio (optional) + httpx TestClient; SQLite in-memory or temp file per test; fixtures for app, auth headers, seed data. Frontend: Vitest + Testing Library + MSW (mock service worker) for query hooks. No live external calls (Chatterbox/LLM mocked).

**Tech Stack:** pytest, pytest-cov, httpx (TestClient), freezegun; frontend: vitest, @testing-library/react, @testing-library/user-event, msw, jsdom.

## Global Constraints

- Tests run offline — all external services (LiteLLM, Chatterbox, Pexels, storage) mocked via dependency injection or monkeypatch
- Each test creates its own DB (temp SQLite file) — no shared state
- Target: backend route coverage ≥ 70% on auth/project/task/voice/presets
- CI-friendly: `pytest` exits nonzero on failure; `vitest run` for frontend
- Don't test FFmpeg output correctness — mock assembly service, assert task state transitions
- Tests added continuously; this phase just bootstraps + covers the critical paths

---

### Task 1: Backend pytest setup

**Files:**
- Create: `money_weaver_backend/tests/__init__.py`
- Create: `money_weaver_backend/tests/conftest.py`
- Create: `money_weaver_backend/pytest.ini`
- Modify: `requirements.txt` (dev deps)

**Interfaces:**
- Produces: `pytest` runs green; `app` fixture, `client` fixture, `auth_headers` fixture

> **NOTE (prep-agent corrections, applied 2026-08-17):** Existing repo has a 48-test unittest suite (`tests/test_user_routes.py`, `test_video_generation_routes.py`, `test_video_tasks_voice.py`, `test_tts_client.py`) running via `python -m unittest`. pytest collects these unchanged. `tests/__init__.py` already exists. The working venv is `venv` (Python 3.13.15); `venv312` is broken. `httpx` 0.28.1 already installed. There is NO `/api/health` route. Storage is a module-level singleton (`_STORAGE`) — must reset `src.services.storage._STORAGE = None` before provider-switch tests.

- [ ] **Step 1: Add dev deps**

```
pytest==8.3.4
pytest-cov==6.0.0
```

(httpx 0.28.1 already present. `pytest-cov` is REQUIRED — `addopts --cov` hard-fails without it.)

Install: `source venv/bin/activate && pip install pytest pytest-cov`

- [ ] **Step 2: pytest.ini**

```ini
[pytest]
testpaths = tests
addopts = -v --cov=src --cov-report=term-missing
python_files = test_*.py
```

- [ ] **Step 3: conftest.py**

```python
import os, tempfile, pytest

# MUST be set at module top, BEFORE any `import src.main`.
# main.py:8 load_dotenv() does NOT override existing env vars, so these win over .env.
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['DATABASE_URL'] = f"sqlite:///{tempfile.mkdtemp(prefix='mw-pytest-')}/test.db"
os.environ['STORAGE_BACKEND'] = 'local'
os.environ['STORAGE_LOCAL_DIR'] = tempfile.mkdtemp(prefix='mw-uploads-')

@pytest.fixture()
def app():
    from src.main import app, db
    from src.main import seed_presets_if_empty  # or copy the seed block from main.py:97-101
    with app.app_context():
        db.create_all()
        seed_presets_if_empty()  # re-seed AFTER drop_all below, or presets disappear after the 1st test
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture()
def client(app):
    return app.test_client()

@pytest.fixture()
def auth_headers(client):
    client.post('/api/auth/register', json={
        'email': 'test@test.com', 'username': 'tester', 'password': 'password123'})
    r = client.post('/api/auth/login', json={
        'email': 'test@test.com', 'password': 'password123'})
    token = r.get_json()['token']
    return {'Authorization': f'Bearer {token}'}
```

- [ ] **Step 4: Sanity test**

```python
# tests/test_auth_smoke.py
def test_no_token_returns_401(client):
    r = client.get('/api/users/me')
    assert r.status_code == 401

def test_health(client):
    # NOTE: /api/health does NOT exist (404). Use the /users/me 401 check above as the sanity test.
    ...
```

- [ ] **Step 5: Verify + commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv/bin/activate
pytest
```

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "test: bootstrap pytest with fixtures"
```

---

### Task 2: Auth + IDOR tests

**Files:**
- Create: `tests/test_auth.py`
- Create: `tests/test_idor.py`

**Interfaces:**
- Produces: tests proving token enforcement + owner-scoping

- [ ] **Step 1: Auth tests**

```python
# test_auth.py
def test_register_login_me_flow(client, auth_headers):
    r = client.get('/api/auth/me', headers=auth_headers)
    assert r.status_code == 200
    assert r.get_json()['email'] == 'test@test.com'

def test_no_token_returns_401(client):
    assert client.get('/api/users/me').status_code == 401

def test_logout_revokes_token(client, auth_headers):
    assert client.post('/api/auth/logout', headers=auth_headers).status_code == 200
    assert client.get('/api/auth/me', headers=auth_headers).status_code == 401

def test_legacy_password_upgrade(client):
    # register, manually set werkzeug hash in db, login still works
    ...
```

- [ ] **Step 2: IDOR tests**

```python
# test_idor.py
def test_cannot_read_other_users_project(client):
    # user A creates project, get id
    # user B (second token) tries GET /api/projects/<a_id> -> 403 (NOT 404 — owner-scoping returns Forbidden)
    ...

def test_cannot_read_other_users_voice(client):
    ...
```

- [ ] **Step 3: Verify + commit**

```bash
pytest tests/test_auth.py tests/test_idor.py
```

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "test: auth and IDOR coverage"
```

---

### Task 3: Presets + tasks + voices tests

**Files:**
- Create: `tests/test_presets.py`
- Create: `tests/test_tasks.py`
- Create: `tests/test_voices.py`

**Interfaces:**
- Produces: coverage for Phase 2/3 routes

- [ ] **Step 1: Presets**

```python
def test_presets_seeded(client, auth_headers):
    r = client.get('/api/presets', headers=auth_headers)
    assert r.status_code == 200
    assert len(r.get_json()) == 6
```

- [ ] **Step 2: Tasks (mock assembly)**

> **NOTE (corrected contract):** `/api/generate/assembler` requires `{project_id, prompt}` (NOT `script`/`duration`), returns **202** with wrapped `{message, task_id, celery_task_id, project_id, settings}`. Route calls **`.delay()`** (NOT `.apply_async`) on `src.tasks.video_tasks.generate_assembler_video_task`; the fake must return an object with `.id` (route reads `celery_task.id`). `task-status/<task_id>` hits Redis — for a DB-only status path use `/api/tasks/<id>/status` (task.py:102) or mock `src.services.celery_app.celery_app.AsyncResult`.

```python
def test_create_assembler_task_sets_user_and_project(client, auth_headers, monkeypatch, mock):
    # monkeypatch src.tasks.video_tasks.generate_assembler_video_task.delay
    #   -> lambda *a, **k: mock.Mock(id='fake-celery-id')
    # POST /api/generate/assembler with {project_id, prompt} -> 202, task_id in body
    # fetch task via /api/tasks/<task_id> -> user_id == current user, project_id set
    ...
```

- [ ] **Step 3: Voices (mock ffprobe/validate_audio)**

> **NOTE (corrected contract):** Voice create is a **JSON** flow, not multipart: (1) `GET /api/uploads/presign?ext=wav` → storage key, (2) `PUT /api/uploads/<key>` with raw bytes, (3) `POST /api/voices` JSON `{name, consent:'true', reference_audio_url: key}`. Route reads `request.get_json(silent=True)`; `reference_audio_url` is required (400 if missing) and validated against `voices/<uid>/<name>.(wav|mp3)`. The create route runs **ffprobe** via `validate_audio` on the fetched bytes — `tts_health` is irrelevant here; mock `src.routes.voices.validate_audio` (returns a duration) instead of uploading real audio.

```python
def test_create_voice_requires_audio(client, auth_headers):
    r = client.post('/api/voices', headers=auth_headers, json={'name': 'V', 'consent': 'true'})
    assert r.status_code == 400  # missing reference_audio_url

def test_create_voice_saves_and_scopes(client, auth_headers, monkeypatch):
    monkeypatch.setattr('src.routes.voices.validate_audio', lambda *a, **k: 1.5)  # duration
    # presign -> PUT upload -> POST /api/voices JSON -> 201, appears in list
    ...
```

- [ ] **Step 4: Verify + commit**

```bash
pytest
```

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "test: presets, task creation, voice routes"
```

---

### Task 4: Storage provider tests

**Files:**
- Create: `tests/test_storage.py`

**Interfaces:**
- Produces: local provider round-trip test; S3 provider mocked with botocore stub

- [ ] **Step 1: Local provider**

> **NOTE (storage singleton):** `get_storage()` lazily reads `STORAGE_BACKEND` once and caches in module-level `_STORAGE` (src/services/storage/__init__.py:6-16). Set `STORAGE_BACKEND`/`STORAGE_LOCAL_DIR` BEFORE first `get_storage()` call in the test, or reset `import src.services.storage as st; st._STORAGE = None` before switching providers. Local files go under `STORAGE_LOCAL_DIR` (default `<backend>/uploads/`) — point it at tmp to avoid polluting the repo. `get_presigned_url` returns a relative `/media/<key>` path (no network).

```python
def test_local_provider_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'local')
    monkeypatch.setenv('STORAGE_LOCAL_DIR', str(tmp_path))
    import src.services.storage as st
    st._STORAGE = None  # ensure fresh provider after env change
    get_storage = st.get_storage
    get_storage().put_object('k.txt', b'data', 'text/plain')
    assert get_storage().object_exists('k.txt')
    assert get_storage().get_presigned_url('k.txt')
    get_storage().delete_object('k.txt')
    assert not get_storage().object_exists('k.txt')
```

> **Optional Step 1b — S3 provider (mocked):** reset `st._STORAGE = None`, set `STORAGE_BACKEND='s3'`, monkeypatch `boto3.client` (or `src.services.storage.s3_provider.boto3.client`) with a stub. Local round-trip above is the required deliverable; S3 stub is nice-to-have. Do NOT make real network calls.

- [ ] **Step 2: Verify + commit**

```bash
pytest tests/test_storage.py
```

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "test: storage provider abstraction"
```

---

### Task 5: Frontend Vitest setup + hook tests

**Files:**
- Create: `money_weaver_frontend/vitest.config.js`
- Create: `money_weaver_frontend/src/test/setup.js`
- Modify: `package.json` (add test script)
- Create: `src/hooks/__tests__/useProjects.test.jsx`

**Interfaces:**
- Produces: `pnpm test` runs hook tests with MSW

- [ ] **Step 1: Install deps**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_frontend
pnpm add -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom msw jsdom
```

- [ ] **Step 2: vitest.config.js**

> **NOTE (critical — alias bug):** The repo path contains a space (`JOHNNY DISK`), so the plan's `new URL('./src', import.meta.url).pathname` returns a **percent-encoded** path (`%20`) that fails to resolve. Copy the WORKING alias from `vite.config.js:11` verbatim: `path.resolve(import.meta.dirname, './src')`. Do NOT add the `tailwindcss()` plugin or `server.proxy` (irrelevant under Vitest).

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
  },
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
})
```

- [ ] **Step 3: setup.js**

> **NOTE:** `api.js` uses an **absolute** base URL `http://localhost:5004/api` (from `VITE_API_URL` in .env), so MSW handlers must use **absolute** URLs or they silently no-op (relative handlers resolve against jsdom origin `http://localhost:3000`). Add `onUnhandledRequest: 'error'` to surface mismatches. jsdom lacks `window.matchMedia` (needed by `use-mobile.js`) — polyfill it. Reset the zustand authStore + localStorage in `afterEach` to avoid cross-test leakage (persist keys: `auth-storage`, `authToken`). eslint has no vitest globals — either import `test/expect/vi` from `'vitest'` in each test file or add a config override.

```js
import '@testing-library/jest-dom/vitest'
import { beforeAll, afterEach, afterAll, vi } from 'vitest'
import { server } from './server'
import { useAuthStore } from '@/store/authStore'

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterEach(() => {
  server.resetHandlers()
  useAuthStore.setState({ user: null, token: null })
  localStorage.clear()
})
afterAll(() => server.close())

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false, media: query,
    addEventListener: vi.fn(), removeEventListener: vi.fn(),
    addListener: vi.fn(), removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})
```

- [ ] **Step 4: MSW handlers + hook test**

> **NOTE:** Derive the base from the same source of truth to avoid drift: `import { API_BASE_URL } from '@/services/api'`. Keep all handlers returning 2xx in happy-path tests — a 401 triggers `window.location.href = '/login'` (jsdom navigation warning).

```js
// src/test/handlers.js
import { http, HttpResponse } from 'msw'
import { API_BASE_URL } from '@/services/api'
const base = API_BASE_URL
export const handlers = [
  http.get(`${base}/projects`, () => HttpResponse.json([{ id: 1, name: 'P' }])),
  http.get(`${base}/users/me`, () => HttpResponse.json({ id: 1, email: 'test@test.com' })),
  http.get(`${base}/api-keys/user/:userId`, () => HttpResponse.json([])),
  http.post(`${base}/api-keys`, () => HttpResponse.json({ id: 1 }, { status: 201 })),
  http.post(`${base}/api-keys/test`, () => HttpResponse.json({ ok: true })),
  http.get(`${base}/tasks/:taskId/status`, () => HttpResponse.json({ status: 'completed', progress: 100 })),
]
```

```jsx
// useProjects.test.jsx
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { useProjects } from '../useProjects'

test('fetches projects', async () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const { result } = renderHook(() => useProjects(), { wrapper: ({ children }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider> })
  await waitFor(() => expect(result.current.data).toHaveLength(1))
})
```

> **Hook test coverage (from prep inventory — one test per hook):** `useProjects` `['projects']`, `useTasks` `['tasks']`, `usePresets` `['presets']`, `useVoices` `['voices']`, `useMe` `['me']`, `useModels` `['models']`, `useDefaultModel` `['models','default']`, `useApiKeys(userId)` `['api-keys', userId]` (requires userId — `enabled: Boolean(userId)`), mutations `useAddApiKey`/`useDeleteApiKey`/`useTestApiKey` (need QueryClientProvider; assert invalidation of `['api-keys', userId]`). `useTaskStatus` is a plain `setInterval` poller (NOT react-query) — use `vi.useFakeTimers()` + advance, or `vi.spyOn(api, 'getTaskStatus')`; don't wait a real 3s interval. `useIsMobile` needs the matchMedia polyfill above.

- [ ] **Step 5: Add script + verify + commit**

`package.json` scripts: `"test": "vitest run"`.

```bash
pnpm test
```

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "test: vitest setup with msw hook tests"
```

---

### Task 6: CI-ready verification

**Files:**
- Create: `.github/workflows/ci.yml` (optional, if repo has remote)

**Interfaces:**
- Produces: documented test commands; full suite passes

- [ ] **Step 1: Document + run all**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend && source venv/bin/activate && pytest
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_frontend && pnpm test
```

Both green.

- [ ] **Step 2: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: phase 6 testing verified"
```
