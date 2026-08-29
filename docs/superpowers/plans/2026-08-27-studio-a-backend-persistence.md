# Studio S1: Backend Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist Studio drafts server-side (`Project.studio_state`) and add the description-generation endpoint, so frontend plans B–F have their API contract.

**Architecture:** Follows existing FastAPI patterns — router in `fastapi_app/routers/`, model in `src/models/project.py`, lightweight column migration in `fastapi_app/main.py` (same style as the existing `thumbnail_path` block). Description route goes in `fastapi_app/routers/enhance.py` (LLM-style route with graceful 503, same as `/api/enhance-prompt`).

**Tech Stack:** FastAPI, SQLAlchemy, pytest + TestClient (existing fixtures in `money_weaver_backend/tests/`).

**Spec:** `docs/superpowers/specs/2026-08-27-studio-flow-design.md`

**Shared contract (used by plans B–F — do not change):**

`studio_state` JSON:
```json
{
  "stage": 1,
  "premise":  { "text": "", "durationSec": 60, "nicheId": "", "sequenceProjectId": null },
  "script":   { "title": "", "description": "", "scriptHtml": "", "characters": [] },
  "storyboard": { "overrides": {} },
  "render":   { "presetId": null, "voiceType": "female", "voiceId": null,
               "voiceModelOverride": null, "workflowType": "assembler",
               "orientation": "landscape", "width": "1920", "height": "1080",
               "language": "en" },
  "updatedAt": "2026-08-27T00:00:00Z"
}
```
`characters` items: `{"name": "JANE", "traits": ["string"]}`. `storyboard.overrides` keys: scene number as string → `{"visualText": "", "imageKey": null, "durationSec": null}`.

---

### Task 1: Project model columns + migration

**Files:**
- Modify: `money_weaver_backend/src/models/project.py`
- Modify: `money_weaver_backend/fastapi_app/main.py` (lifespan lightweight migration block, after existing `thumbnail_path` block)
- Test: `money_weaver_backend/tests/test_studio_state_model.py`

- [ ] **Step 1: Failing test**

```python
def test_project_has_studio_state_columns():
    from src.models.project import Project
    cols = {c.name for c in Project.__table__.columns}
    assert 'studio_state' in cols
    assert 'schema_version' in cols
```

- [ ] **Step 2: Run RED**

Run from `money_weaver_backend/`: `python -m pytest tests/test_studio_state_model.py -q`
Expected: FAIL (AttributeError on import or missing column assertion).

- [ ] **Step 3: Implement**

In `src/models/project.py`, add to the Project class:

```python
    studio_state = db.Column(db.Text, nullable=True)          # JSON draft state for Studio
    schema_version = db.Column(db.Integer, default=1, nullable=False)
```

(Use the same `db` import the file already uses.)

In `fastapi_app/main.py` lifespan, after the existing `thumbnail_path` block, add an equivalent lightweight migration:

```python
    _cols = [c['name'] for c in _inspect(engine).get_columns('project')]
    with engine.connect() as _conn:
        if 'studio_state' not in _cols:
            _conn.execute(_text("ALTER TABLE project ADD COLUMN studio_state TEXT"))
        if 'schema_version' not in _cols:
            _conn.execute(_text(
                "ALTER TABLE project ADD COLUMN schema_version INTEGER DEFAULT 1 NOT NULL"
            ))
        _conn.commit()
```

- [ ] **Step 4: GREEN** — same command passes.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/models/project.py money_weaver_backend/fastapi_app/main.py money_weaver_backend/tests/test_studio_state_model.py
git commit -m "feat: Project.studio_state + schema_version columns (lightweight migration)"
```

---

### Task 2: Studio endpoints (create draft, GET, PUT)

**Files:**
- Modify: `money_weaver_backend/fastapi_app/routers/projects.py`
- Test: `money_weaver_backend/tests/test_studio_endpoints.py`

Route summary:
- `POST /api/projects/studio` → 201: creates Project (title='Studio Draft', workflow_type='assembler', studio_state=NULL) for current user, returns project dict.
- `GET /api/projects/{id}/studio` → 200 `{"studio_state": <parsed json>}`. 404 if project missing; 403 if not owner; 404 if studio_state NULL (no draft yet).
- `PUT /api/projects/{id}/studio` → body = full state dict → stores `json.dumps`, touches nothing else, returns `{"saved_at": iso}`.

- [ ] **Step 1: Failing tests**

```python
import json

from fastapi.testclient import TestClient
from fastapi_app.main import app


def _auth(client, email):
    r = client.post('/api/auth/register', json={
        'email': email, 'username': email.split('@')[0], 'password': 'Passw0rd!x'})
    assert r.status_code == 201
    return {'Authorization': f"Bearer {r.json()['token']}"}, r.json()['user']


def test_studio_create_get_put_round_trip():
    client = TestClient(app)
    auth, user = _auth(client, 'studio-rt@example.com')

    r = client.post('/api/projects/studio', headers=auth)
    assert r.status_code == 201
    pid = r.json()['id']

    # No draft yet
    r = client.get(f'/api/projects/{pid}/studio', headers=auth)
    assert r.status_code == 404

    state = {'stage': 1, 'premise': {'text': 'cats'}, 'script': {},
             'storyboard': {'overrides': {}}, 'render': {}, 'updatedAt': '2026-08-27T00:00:00Z'}
    r = client.put(f'/api/projects/{pid}/studio', headers=auth, json=state)
    assert r.status_code == 200
    assert 'saved_at' in r.json()

    r = client.get(f'/api/projects/{pid}/studio', headers=auth)
    assert r.status_code == 200
    assert r.json()['studio_state'] == state


def test_studio_endpoints_enforce_ownership():
    client = TestClient(app)
    auth_a, _ = _auth(client, 'studio-a@example.com')
    auth_b, _ = _auth(client, 'studio-b@example.com')

    pid = client.post('/api/projects/studio', headers=auth_a).json()['id']
    assert client.get(f'/api/projects/{pid}/studio', headers=auth_b).status_code in (403, 404)
    assert client.put(f'/api/projects/{pid}/studio', headers=auth_b,
                      json={'stage': 2}).status_code in (403, 404)
    assert client.get('/api/projects/999999/studio', headers=auth_a).status_code == 404
    # Unauthenticated
    assert client.post('/api/projects/studio').status_code in (401, 403)
```

- [ ] **Step 2: Run RED** — `python -m pytest tests/test_studio_endpoints.py -q` fails (404s missing).

- [ ] **Step 3: Implement** in `fastapi_app/routers/projects.py`:

```python
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends  # existing imports
from fastapi_app.db import get_db
from fastapi_app.deps import current_user
from src.models.project import Project


@router.post('/studio', status_code=201)
def create_studio_draft(user=Depends(current_user), session=Depends(get_db)):
    project = Project(title='Studio Draft', description='',
                      user_id=user.id, workflow_type='assembler')
    session.add(project)
    session.commit()
    return project.to_dict()


@router.get('/{project_id}/studio')
def get_studio_state(project_id: int, user=Depends(current_user), session=Depends(get_db)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    if project.studio_state is None:
        raise HTTPException(404, 'No studio draft')
    return {'studio_state': json.loads(project.studio_state)}


@router.put('/{project_id}/studio')
def put_studio_state(project_id: int, body: dict,
                     user=Depends(current_user), session=Depends(get_db)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(404, 'Not found')
    if project.user_id != user.id:
        raise HTTPException(403, 'Forbidden')
    project.studio_state = json.dumps(body)
    project.schema_version = int(body.get('schemaVersion', project.schema_version or 1))
    session.commit()
    return {'saved_at': datetime.now(timezone.utc).isoformat()}
```

Note: register route order so `'/studio'` (static) is declared BEFORE `'/{project_id}/...'` dynamic routes — FastAPI matches in declaration order; otherwise `studio` gets parsed as `{project_id}` and 422s.

- [ ] **Step 4: GREEN** — `python -m pytest tests/test_studio_endpoints.py -q` passes.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/fastapi_app/routers/projects.py money_weaver_backend/tests/test_studio_endpoints.py
git commit -m "feat: studio draft endpoints — create/GET/PUT studio_state with ownership"
```

---

### Task 3: Description generation route

**Files:**
- Modify: `money_weaver_backend/fastapi_app/routers/enhance.py`
- Test: `money_weaver_backend/tests/test_generate_description.py`

Behavior: `POST /api/generate/description {premise, script}` → `{"description": str}`. 400 without premise; LLM failure → 503 (same graceful pattern as enhance-prompt).

- [ ] **Step 1: Failing tests**

```python
from fastapi.testclient import TestClient
from fastapi_app.main import app


def _auth(client, email):
    r = client.post('/api/auth/register', json={
        'email': email, 'username': email.split('@')[0], 'password': 'Passw0rd!x'})
    return {'Authorization': f"Bearer {r.json()['token']}"}


def test_description_requires_premise():
    client = TestClient(app)
    auth = _auth(client, 'desc-1@example.com')
    r = client.post('/api/generate/description', headers=auth, json={})
    assert r.status_code == 400


def test_description_503_without_provider(monkeypatch):
    monkeypatch.setenv('ALLOW_NO_KEY_503', '1')  # documents intent; not read by code
    client = TestClient(app)
    auth = _auth(client, 'desc-2@example.com')
    r = client.post('/api/generate/description', headers=auth,
                    json={'premise': 'cats learn to code'})
    # Without any LLM key configured this must degrade to 503, never 500
    assert r.status_code in (503, 200)
    assert r.status_code < 500
```

- [ ] **Step 2: Run RED** — fails 404.

- [ ] **Step 3: Implement** — append to `fastapi_app/routers/enhance.py`:

```python
@router.post('/generate/description')
def generate_description(body: dict, user=Depends(current_user)):
    premise = (body.get('premise') or '').strip()
    if not premise:
        raise HTTPException(400, 'premise is required')
    script = (body.get('script') or '').strip()[:2000]
    model = llm_service.resolve_model_for(user.id, 'script')
    try:
        description = llm_service._chat_free_resilient(
            user.id, model,
            [{"role": "system", "content":
              "You write one-paragraph platform video descriptions (<=80 words), "
              "no hashtags unless asked. Return ONLY the description text."},
             {"role": "user", "content":
              f"Premise: {premise}\n\nScript excerpt:\n{script or '(none yet)'}"}],
            temperature=0.7, max_tokens=200)
        return {"description": (description or '').strip()}
    except Exception as e:
        raise HTTPException(503, f"Description generation unavailable: {e}")
```

- [ ] **Step 4: GREEN** — `python -m pytest tests/test_generate_description.py -q` passes.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/fastapi_app/routers/enhance.py money_weaver_backend/tests/test_generate_description.py
git commit -m "feat: POST /api/generate/description (premise+script → description, graceful 503)"
```

---

### Task 4: Close-out

- [ ] **Step 1: Full backend suite green**

Run from `money_weaver_backend/`: `python -m pytest -q` — expect 408+N passed, coverage ≥55%.

- [ ] **Step 2: Update `.superpowers/sdd/progress.md`** — append one dated line: `S1 studio backend persistence — commits <shas>`.

- [ ] **Step 3: Commit + push**

```bash
git commit -m "chore: S1 studio backend persistence close-out"
git push origin main
```
