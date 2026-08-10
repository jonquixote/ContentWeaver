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

- [ ] **Step 1: Add dev deps**

```
pytest==8.3.4
pytest-cov==6.0.0
httpx==0.28.1
```

Install: `pip install pytest pytest-cov httpx`

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
os.environ['SECRET_KEY'] = 'test-secret'
os.environ['DATABASE_URL'] = f'sqlite:///{tempfile.mkdtemp()}/test.db'
os.environ['STORAGE_BACKEND'] = 'local'

@pytest.fixture()
def app():
    from src.main import app, db
    with app.app_context():
        db.create_all()
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
def test_health(client):
    r = client.get('/api/health')
    assert r.status_code == 200
```

- [ ] **Step 5: Verify + commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv312/bin/activate
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
    # user B (second token) tries GET /api/projects/<a_id> -> 404
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

Monkeypatch `src.tasks.video_tasks.generate_assembler_video_task` OR assert task created + status transitions:

```python
def test_create_assembler_task_sets_user_and_project(client, auth_headers, monkeypatch):
    def fake_run(task_id):
        return {'task_id': task_id, 'status': 'queued'}
    monkeypatch.setattr('src.tasks.video_tasks.generate_assembler_video_task.apply_async', fake_run)
    r = client.post('/api/generate/assembler', headers=auth_headers,
                    json={'script': 'Title: T\nFull Narrative: A tip.', 'duration': 15})
    assert r.status_code == 200
    tid = r.get_json()['task_id']
    # fetch task -> has user_id == current user, project_id set
```

- [ ] **Step 3: Voices (mock TTS client)**

```python
def test_create_voice_requires_audio(client, auth_headers):
    r = client.post('/api/voices', headers=auth_headers,
                    data={'name': 'V'}, content_type='multipart/form-data')
    assert r.status_code == 400  # missing reference_audio

def test_create_voice_saves_and_scopes(client, auth_headers, monkeypatch):
    monkeypatch.setattr('src.services.tts_client.tts_health', lambda: True)
    # upload tiny wav bytes -> 201, appears in list
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

```python
def test_local_provider_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv('STORAGE_BACKEND', 'local')
    from src.services.storage import get_storage
    get_storage().put_object('k.txt', b'data', 'text/plain')
    assert get_storage().object_exists('k.txt')
    assert get_storage().get_presigned_url('k.txt')
    get_storage().delete_object('k.txt')
    assert not get_storage().object_exists('k.txt')
```

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

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    css: false,
  },
  resolve: { alias: { '@': new URL('./src', import.meta.url).pathname } },
})
```

- [ ] **Step 3: setup.js**

```js
import '@testing-library/jest-dom/vitest'
import { server } from './server'  // MSW server
beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```

- [ ] **Step 4: MSW handlers + hook test**

```js
// src/test/handlers.js
import { http, HttpResponse } from 'msw'
export const handlers = [
  http.get('/api/projects', () => HttpResponse.json([{ id: 1, name: 'P' }])),
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
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend && source venv312/bin/activate && pytest
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_frontend && pnpm test
```

Both green.

- [ ] **Step 2: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: phase 6 testing verified"
```
