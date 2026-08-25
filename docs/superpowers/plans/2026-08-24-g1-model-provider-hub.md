# G1: Model & Provider Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Searchable provider-aware model catalog plus per-task assignments (idea/script/enhance/voice_tts/video_gen) that generative features respect, with fal.ai as the first API voice/video provider.

**Architecture:** Extend the existing `ModelRegistry` protocol with `kind` tags; add a fal.ai adapter mirroring `comfy_client`'s submit/poll/download flow; new `model_assignment` table resolved through `resolve_model_for(user_id, task)` with precedence assignment → ModelPreference.defaults → registry default; one reusable `<ModelPicker>` React component powering Settings card + wizard overrides.

**Tech Stack:** SQLAlchemy + Alembic (head `b7e1d2c3a4f5`), FastAPI, fal-client 1.0.1 (Apache-2.0, optional install), react-query + msw (existing frontend stack).

**Repo facts:** Root `/Volumes/JOHNNY DISK/MoneyWeaver` (quote paths). Python: `money_weaver_backend/venv/bin/python -m pytest`. Baseline **381 backend** / **25 frontend** tests green. Frontend tests: `cd money_weaver_frontend && npx vitest run`; build `npx vite build`. Existing patterns to copy: ApiKey encrypted storage (`fastapi_app/routers/api_keys.py:40-60`, `src/services/key_encryption.py`), registry (`src/services/providers/registry.py`), comfy gateway flow (`src/services/comfy_client.py`, video_tasks enabled branch ~600-640), Settings page cards (`money_weaver_frontend/src/components/SettingsPage.jsx`), hooks (`src/hooks/useNiches.js`). macOS AppleDouble `._*` files on this volume break alembic — if alembic errors with null-bytes SyntaxError, run `find money_weaver_backend/migrations -name '._*' -delete` first.

---

### Task 1: model_assignment table + resolution + routes

**Files:**
- Create: `money_weaver_backend/src/models/model_assignment.py`
- Create: `money_weaver_backend/migrations/versions/c8f2e3d4a5b6_model_assignment.py`
- Modify: `money_weaver_backend/src/services/llm_service.py` (add resolve helper near api_key_for)
- Modify: `money_weaver_backend/fastapi_app/routers/settings.py` (assignments routes)
- Test: `money_weaver_backend/tests/test_model_assignments.py`

- [ ] **Step 1: Write failing tests**

Create `money_weaver_backend/tests/test_model_assignments.py`:

```python
VALID_TASKS = {"idea", "script", "enhance", "voice_tts", "video_gen"}


def test_put_and_get_assignments(client, auth_headers):
    r = client.put('/api/model-assignments', headers=auth_headers,
                   json={"assignments": {"idea": "poolside/laguna-s-2.1:free",
                                          "video_gen": "fal-ai/wan-t2v"}})
    assert r.status_code == 200
    r = client.get('/api/model-assignments', headers=auth_headers)
    assert r.status_code == 200
    a = r.json()['assignments']
    assert a['idea'] == 'poolside/laguna-s-2.1:free'
    assert a['video_gen'] == 'fal-ai/wan-t2v'


def test_put_rejects_unknown_task(client, auth_headers):
    r = client.put('/api/model-assignments', headers=auth_headers,
                   json={"assignments": {"bogus_task": "x"}})
    assert r.status_code == 400


def test_resolve_precedence_assignment_over_prefs(client, auth_headers, db_session, monkeypatch):
    from src.services.llm_service import resolve_model_for
    from src.models.model_assignment import ModelAssignment
    from src.models.model_preference import ModelPreference
    uid = client.get('/api/users/me', headers=auth_headers).json()['id']
    db_session.add(ModelAssignment(user_id=uid, task='script', model_id='assigned/model'))
    db_session.add(ModelPreference(user_id=uid, defaults='{"script": "pref/model"}',
                                   fallbacks='[]'))
    db_session.commit()
    assert resolve_model_for(uid, 'script') == 'assigned/model'


def test_resolve_falls_back_to_prefs_then_default(client, auth_headers, db_session, monkeypatch):
    from src.services.llm_service import resolve_model_for
    from src.models.model_preference import ModelPreference
    from src.services.providers import registry as reg_mod
    uid = client.get('/api/users/me', headers=auth_headers).json()['id']
    db_session.add(ModelPreference(user_id=uid, defaults='{"script": "pref/model"}',
                                   fallbacks='[]'))
    db_session.commit()
    monkeypatch.setattr(reg_mod.registry, 'best_free',
                        lambda capability='chat': 'poolside/laguna-s-2.1:free')
    assert resolve_model_for(uid, 'script') == 'pref/model'          # prefs win over default-free
    assert resolve_model_for(uid, 'enhance') == 'poolside/laguna-s-2.1:free'  # registry default


def test_resolve_voice_video_defaults():
    from src.services.llm_service import resolve_model_for
    import os
    from unittest import mock
    with mock.patch.dict(os.environ, {'COMFY_ENABLED': ''}):
        assert resolve_model_for(None, 'voice_tts') == 'auto'
        assert resolve_model_for(None, 'video_gen').startswith('fal-ai/')
```

Add missing import at top of file if linters demand: none needed beyond what's shown.
Note: `resolve_model_for(None, ...)` must not touch DB for None user.

- [ ] **Step 2: Run tests to verify they fail**

Run: `money_weaver_backend/venv/bin/python -m pytest money_weaver_backend/tests/test_model_assignments.py -v --no-cov`
Expected: FAIL — ModuleNotFoundError `src.models.model_assignment`; 404 on routes.

- [ ] **Step 3: Implement model**

Create `money_weaver_backend/src/models/model_assignment.py`:

```python
from datetime import datetime

from fastapi_app.db import get_db

get_db_instance = get_db()


class ModelAssignment(get_db_instance.Model):
    __tablename__ = 'model_assignment'

    id = get_db_instance.Column(get_db_instance.Integer, primary_key=True)
    user_id = get_db_instance.Column(get_db_instance.Integer,
                                     get_db_instance.ForeignKey('user.id'),
                                     nullable=False)
    task = get_db_instance.Column(get_db_instance.String(32), nullable=False)
    model_id = get_db_instance.Column(get_db_instance.String(255), nullable=False)
    created_at = get_db_instance.Column(get_db_instance.DateTime, default=datetime.utcnow)
    updated_at = get_db_instance.Column(get_db_instance.DateTime,
                                        default=datetime.utcnow,
                                        onupdate=datetime.utcnow)

    class Meta:
        unique_constraint = ('user_id', 'task')
```

IMPORTANT adaptation: match how OTHER models in this codebase declare columns (grep
`class Project` in `src/models/project.py` — they call `get_db()` directly inside Column
definitions, e.g. `get_db().Column(...)`). Replicate that exact idiom and add
`__table_args__ = (get_db().UniqueConstraint('user_id', 'task'),)` following whatever
UniqueConstraint import style works with the project's Flask-SQLAlchemy instance. Verify by
importing the module before writing the migration.

- [ ] **Step 4: Migration**

Create `money_weaver_backend/migrations/versions/c8f2e3d4a5b6_model_assignment.py` copying the
header/style of `b7e1d2c3a4f5_project_transcript.py`:

```python
revision: str = 'c8f2e3d4a5b6'
down_revision: Union[str, Sequence[str], None] = 'b7e1d2c3a4f5'

def upgrade() -> None:
    op.create_table(
        'model_assignment',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('task', sa.String(length=32), nullable=False),
        sa.Column('model_id', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'task', name='uq_model_assignment_user_task'),
    )

def downgrade() -> None:
    op.drop_table('model_assignment')
```

Then run: `find money_weaver_backend/migrations -name '._*' -delete` and
`cd money_weaver_backend && venv/bin/python -m alembic upgrade head` — must succeed.

- [ ] **Step 5: Resolution helper**

In `llm_service.py` (module level, after imports):

```python
ASSIGNMENT_TASKS = ("idea", "script", "enhance", "voice_tts", "video_gen")
DEFAULT_VIDEO_GEN_FALLBACK = "fal-ai/wan-t2v-v2.2"


def resolve_model_for(user_id, task):
    """assignment -> ModelPreference.defaults[task] -> sensible default."""
    if task not in ASSIGNMENT_TASKS:
        raise ValueError(f"unknown assignment task: {task}")
    if user_id:
        try:
            from src.models.model_assignment import ModelAssignment
            from src.services.providers.registry import (
                PREFERRED_FREE_MODELS, UNUSABLE_MODEL_IDS)
            from fastapi_app.db import db_session
            with db_session() as session:
                row = session.query(ModelAssignment).filter_by(
                    user_id=user_id, task=task).first()
                if row is not None and row.model_id:
                    return row.model_id
                from src.models.model_preference import ModelPreference
                pref = session.query(ModelPreference).filter_by(user_id=user_id).first()
                if pref is not None and pref.defaults:
                    import json as _json
                    val = (_json.loads(pref.defaults) or {}).get(task)
                    if val:
                        return val
        except Exception as e:
            print(f"resolve_model_for({task}) lookup failed: {e}")
    # Defaults (no user or nothing stored)
    if task in ("voice_tts",):
        return "auto"
    if task == "video_gen":
        import os
        if os.getenv('COMFY_ENABLED', 'false').lower() != 'true':
            return DEFAULT_VIDEO_GEN_FALLBACK
        return "comfy_local"
    return _registry.best_free() or PREFERRED_FREE_MODELS[0]
```

Note: `_registry.best_free()` already excludes pseudo-ids via UNUSABLE_MODEL_IDS; the import of
UNUSABLE_MODEL_IDS here is only needed if you extend logic — drop unused imports rather than
keeping dead references.

- [ ] **Step 6: Routes**

In `fastapi_app/routers/settings.py` append:

```python
from fastapi import HTTPException  # if not already imported
from src.services.llm_service import ASSIGNMENT_TASKS

@router.get('/model-assignments')
def get_assignments(user=Depends(current_user), session=Depends(get_db)):
    from src.models.model_assignment import ModelAssignment
    rows = session.query(ModelAssignment).filter_by(user_id=user.id).all()
    return {"assignments": {r.task: r.model_id for r in rows}}


@router.put('/model-assignments')
def put_assignments(body: dict, user=Depends(current_user), session=Depends(get_db)):
    from src.models.model_assignment import ModelAssignment
    assignments = body.get('assignments') or {}
    bad = [t for t in assignments if t not in ASSIGNMENT_TASKS]
    if bad:
        raise HTTPException(400, f"unknown tasks: {bad}")
    for task, model_id in assignments.items():
        if not isinstance(model_id, str) or not model_id.strip():
            raise HTTPException(400, f"invalid model_id for {task}")
        row = session.query(ModelAssignment).filter_by(
            user_id=user.id, task=task).first()
        if row:
            row.model_id = model_id.strip()
        else:
            session.add(ModelAssignment(user_id=user.id, task=task,
                                        model_id=model_id.strip()))
    session.commit()
    return {"ok": True}
```

Match the file's existing imports/style (read settings.py header first). Register nothing new —
settings router already included in main.py.

- [ ] **Step 7: Run tests**

Focused then full suite (`381+` green expected).

- [ ] **Step 8: Commit**

```bash
git add money_weaver_backend/src/models/model_assignment.py money_weaver_backend/migrations/versions/c8f2e3d4a5b6_model_assignment.py money_weaver_backend/src/services/llm_service.py money_weaver_backend/fastapi_app/routers/settings.py money_weaver_backend/tests/test_model_assignments.py
git commit -m "feat: model_assignment table + resolve_model_for + GET/PUT /api/model-assignments"
```

---

### Task 2: Catalog kind tags + filtered GET /api/models

**Files:**
- Modify: `money_weaver_backend/src/services/providers/openrouter.py` (add kind:'text' in list_models entries)
- Modify: `money_weaver_backend/fastapi_app/routers/api_keys.py` (models route ~167: q/kind filters)
- Test: `money_weaver_backend/tests/test_models_endpoint.py`

- [ ] **Step 1: Write failing tests**

Create `money_weaver_backend/tests/test_models_endpoint.py`:

```python
CATALOG = [
    {"id": "a/text-model", "provider": "openrouter", "display_name": "A Text",
     "capabilities": {"chat": True}, "free": False, "kind": "text"},
    {"id": "b/free-text", "provider": "openrouter", "display_name": "B Free",
     "capabilities": {"chat": True}, "free": True, "kind": "text"},
]


def test_models_filter_kind_and_q(client, auth_headers, monkeypatch):
    from fastapi_app.routers import api_keys
    monkeypatch.setattr(api_keys.registry, 'list_models', lambda force=False: CATALOG)
    r = client.get('/api/models?kind=text&q=free', headers=auth_headers)
    ids = [m['id'] for m in r.json()['models']]
    assert ids == ['b/free-text']


def test_models_entries_carry_kind(client, auth_headers, monkeypatch):
    from fastapi_app.routers import api_keys
    monkeypatch.setattr(api_keys.registry, 'list_models', lambda force=False: CATALOG)
    r = client.get('/api/models', headers=auth_headers)
    assert all('kind' in m and m['kind'] in ('text', 'voice', 'video')
               for m in r.json()['models'])
```

- [ ] **Step 2: RED** — run focused; expect missing filter behavior/kind passthrough failures.

- [ ] **Step 3: Implement**

openrouter.list_models: add `"kind": "text"` to each dict.
api_keys models route:

```python
@router.get('/models')
def available_models(kind: Optional[str] = None, q: Optional[str] = None,
                     user=Depends(current_user)):
    """Get available models from the registry (live, cache-backed)"""
    models = registry.list_models()
    if kind:
        models = [m for m in models if m.get('kind') == kind]
    if q:
        needle = q.lower()
        models = [m for m in models
                  if needle in m['id'].lower()
                  or needle in (m.get('display_name') or '').lower()]
    return {"models": models}
```

Preserve the route's existing auth dependencies exactly as found.

- [ ] **Step 4: GREEN + full suite**
- [ ] **Step 5: Commit** `feat: kind tags + search/filter on GET /api/models`

---

### Task 3: fal adapter

**Files:**
- Create: `money_weaver_backend/src/services/providers/fal_adapter.py`
- Modify: `money_weaver_backend/requirements.txt` (commented optional block)
- Test: `money_weaver_backend/tests/test_fal_adapter.py`

- [ ] **Step 1: License/version verification (blocking gate)**

Run: `curl -s https://pypi.org/pypi/fal-client/json | python3 -c "import json,sys; d=json.load(sys.stdin)['info']; print(d['version']); print(d.get('license'))"`
and `curl -s https://raw.githubusercontent.com/fal-ai/fal/main/LICENSE | head -1`.
Expect version ≥1.0.1 and Apache-2.0. If license differs → STOP, report BLOCKED.

- [ ] **Step 2: Write failing tests**

Create `money_weaver_backend/tests/test_fal_adapter.py`:

```python
import pytest


@pytest.fixture
def fake_fal(monkeypatch):
    """Fake fal_client module: submit returns handle, status/result recorded."""
    import sys, types
    calls = {}
    mod = types.ModuleType("fal_client")
    mod.submit = lambda app, argument, api_key=None: calls.update(
        app=app, argument=argument, api_key=api_key) or types.SimpleNamespace(
        request_id="req-123")
    def _status(app, request_id, logs=False):
        calls['status_polls'] = calls.get('status_polls', 0) + 1
        if calls['status_polls'] < 2:
            return types.SimpleNamespace(status="IN_QUEUE")
        class Done:
            status = "COMPLETED"
        return Done()
    mod.status = _status
    mod.result = lambda app, request_id: calls.update(result=True) or {
        "video": {"url": "https://fake.cdn/out.mp4"}}
    monkeypatch.setitem(sys.modules, "fal_client", mod)
    return calls


def test_list_catalog_has_kinds():
    from src.services.providers.fal_adapter import FAL_CATALOG
    kinds = {e["kind"] for e in FAL_CATALOG}
    assert "voice" in kinds and "video" in kinds
    assert all(e["provider"] == "fal" and e["id"].startswith("fal-ai/")
               for e in FAL_CATALOG)


def test_submit_and_download(monkeypatch, tmp_path, fake_fal):
    from src.services.providers import fal_adapter
    monkeypatch.setattr(fal_adapter, "_download", lambda url, dest: dest.write_bytes(b"MP4"))
    out = fal_adapter.render("fal-ai/wan-t2v", {"prompt": "cat"},
                             api_key="FAKE", work_dir=str(tmp_path))
    assert fake_fal["app"] == "fal-ai/wan-t2v"
    assert fake_fal["argument"] == {"prompt": "cat"}
    assert fake_fal["api_key"] == "FAKE"
    assert out.endswith(".mp4") and (tmp_path / "out.mp4").exists() or True
    # exact assertion:
    import os
    assert os.path.exists(out) and os.path.getsize(out) > 0


def test_missing_api_key_raises(monkeypatch):
    from src.services.providers import fal_adapter
    monkeypatch.setattr(fal_adapter, "_key_for", lambda: None)
    with pytest.raises(RuntimeError, match="FAL key"):
        fal_adapter.render("fal-ai/x", {})
```

- [ ] **Step 3: RED**
- [ ] **Step 4: Implement** `fal_adapter.py`:

```python
"""fal.ai voice/video generation adapter (fal-client, Apache-2.0).

Optional dependency: pip install fal-client. Keys stored per-user via the
ApiKey table (provider='fal'), decrypted by callers; env FAL_KEY as fallback.
"""
import os
import time
import uuid


FAL_CATALOG = [
    {"id": "fal-ai/wan-t2v", "provider": "fal", "kind": "video",
     "display_name": "Wan 2.2 T2V (fal)", "free": False},
    {"id": "fal-ai/minimax/video-01", "provider": "fal", "kind": "video",
     "display_name": "MiniMax Video 01 (fal)", "free": False},
    {"id": "fal-ai/kokoro-tts", "provider": "fal", "kind": "voice",
     "display_name": "Kokoro TTS (fal)", "free": False},
]


def _key_for():
    return os.getenv("FAL_KEY")


def _download(url, dest_path):
    import httpx
    with httpx.stream("GET", url, timeout=300) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as fh:
            for chunk in r.iter_bytes():
                fh.write(chunk)
    return dest_path


def render(endpoint, arguments, api_key=None, work_dir="/tmp", timeout_s=600):
    """Submit to fal, poll until COMPLETED, download first media URL.

    Returns local file path. Raises RuntimeError on misconfig/timeout."""
    if not api_key:
        raise RuntimeError("FAL key unavailable (save a fal API key or set FAL_KEY)")
    import fal_client
    handle = fal_client.submit(endpoint, arguments, api_key=api_key)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = fal_client.status(endpoint, handle.request_id)
        if getattr(status, "status", "") == "COMPLETED":
            break
        time.sleep(2)
    else:
        raise RuntimeError(f"fal render timed out after {timeout_s}s")
    result = fal_client.result(endpoint, handle.request_id)
    url = _extract_url(result)
    if not url:
        raise RuntimeError(f"no media url in fal result: {str(result)[:200]}")
    dest = os.path.join(work_dir, f"fal_{uuid.uuid4().hex}.mp4")
    return _download(url, dest)


def _extract_url(result):
    def walk(node):
        if isinstance(node, dict):
            if node.get("url") and str(node.get("content_type", "")).startswith(("video/", "audio/")):
                return node["url"]
            for v in node.values():
                found = walk(v)
                if found:
                    return found
        elif isinstance(node, list):
            for v in node:
                found = walk(v)
                if found:
                    return found
        return None
    return walk(result)


def catalog_models():
    return [dict(e) for e in FAL_CATALOG]
```

Adapt `_extract_url` after inspecting real fal response shapes documented at
https://docs.fal.ai/model-endpoints/queue — the walker handles nested video/audio dicts.

- [ ] **Step 5: requirements.txt** — commented block after chatterbox one:

```text
# --- Optional: fal.ai voice/video generation (fal-client, Apache-2.0) ---
#   pip install fal-client==1.0.1   # verify latest via PyPI before enabling
# Per-user keys via API keys page (provider 'fal') or env FAL_KEY.
```

- [ ] **Step 6: GREEN + full suite**
- [ ] **Step 7: Commit** `feat: fal.ai adapter — catalog, submit/poll/download (Apache-2.0, optional dep)`

---

### Task 4: Merge fal catalog into registry + key-added hook

**Files:**
- Modify: `money_weaver_backend/src/services/providers/registry.py` (merge non-text providers)
- Modify: `money_weaver_backend/fastapi_app/routers/api_keys.py` (POST /api-keys warms catalog)
- Test: `money_weaver_backend/tests/test_registry_merge.py`

- [ ] **Step 1: Failing tests**

Create `money_weaver_backend/tests/test_registry_merge.py`:

```python
def test_list_models_includes_fal_catalog(monkeypatch):
    from src.services.providers import registry as reg_mod
    from src.services.providers.fal_adapter import FAL_CATALOG
    monkeypatch.setattr(reg_mod.registry, '_cache', None)
    monkeypatch.setattr(reg_mod.registry, '_fetched_at', 0.0)
    monkeypatch.setattr(reg_mod, 'EXTRA_CATALOG_SOURCES', [
        lambda: FAL_CATALOG,
        lambda: (_ for _ in ()).throw(RuntimeError("down")),
    ])
    models = reg_mod.registry.list_models(force=True)
    ids = {m['id'] for m in models}
    assert 'fal-ai/wan-t2v' in ids


def test_adding_fal_key_invalidates_cache(client, auth_headers, monkeypatch):
    from fastapi_app.routers import api_keys
    from src.services.providers import registry as reg_mod
    warmed = {}
    monkeypatch.setattr(api_keys, 'warm_provider_catalogs',
                        lambda: warmed.setdefault('called', True))
    r = client.post('/api/api-keys', headers=auth_headers,
                    json={'name': 'FAL', 'provider': 'fal', 'key': 'fake-fal-key'})
    assert r.status_code == 201
    assert warmed.get('called') is True
```

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement**

registry.list_models: after provider loop, merge extras:

```python
for source in EXTRA_CATALOG_SOURCES:
    try:
        for m in source():
            if m["id"] not in seen:
                seen.add(m["id"])
                merged.append(m)
    except Exception:
        continue
```

with module-level `EXTRA_CATALOG_SOURCES = []` and in fal_adapter bottom:
`from src.services.providers.registry import EXTRA_CATALOG_SOURCES; EXTRA_CATALOG_SOURCES.append(catalog_models)` — guard against double-append with an idempotency flag on the function (`getattr(catalog_models, '_registered', False)`).

api_keys POST handler: after successful commit, call module-level
`warm_provider_catalogs()` defined as:

```python
def warm_provider_catalogs():
    """Invalidate cached catalog so newly-keyed providers appear immediately."""
    try:
        registry.list_models(force=True)
    except Exception:
        pass
```

- [ ] **Step 4: GREEN + full suite**
- [ ] **Step 5: Commit** `feat: merge fal catalog into registry; key-add warms catalogs`

---

### Task 5: `<ModelPicker>` component

**Files:**
- Create: `money_weaver_frontend/src/components/ModelPicker.jsx`
- Create: `money_weaver_frontend/src/hooks/useModels.js`
- Test: `money_weaver_frontend/src/__tests__/modelPicker.test.jsx`
- Modify: `money_weaver_frontend/src/test/handlers.js` (msw handler for /api/models)

- [ ] **Step 1: Failing component tests** (follow nichePicker.test.jsx conventions exactly — read it first):

```jsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react"
import ModelPicker from "@/components/ModelPicker"

const MODELS = [
  { id: "poolside/laguna-s-2.1:free", label: "Laguna S 2.1", provider: "openrouter",
    kind: "text", free: true },
  { id: "fal-ai/wan-t2v", label: "Wan 2.2 T2V (fal)", provider: "fal",
    kind: "video", free: false },
]

function setup(props = {}) {
  return render(<ModelPicker models={MODELS} value={null} onChange={() => {}} {...props} />)
}

test("renders search box and provider chips", () => {
  setup()
  expect(screen.getByPlaceholderText(/search models/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /all/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /openrouter/i })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /fal/i })).toBeInTheDocument()
})

test("search filters by id and label", () => {
  setup()
  fireEvent.change(screen.getByPlaceholderText(/search models/i), { target: { value: 'laguna' } })
  expect(screen.getByText(/laguna/i)).toBeInTheDocument()
  expect(screen.queryByText(/wan 2\.2/i)).not.toBeInTheDocument()
})

test("clicking option calls onChange with id", async () => {
  const onChange = vi.fn()
  setup({ onChange })
  fireEvent.click(screen.getByText(/wan 2\.2/i))
  expect(onChange).toHaveBeenCalledWith("fal-ai/wan-t2v")
})
```

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement**

`useModels.js` mirrors useNiches.js (react-query GET `/models` via ApiService; add
`getModels(params)` to `src/services/api.js` building querystring).

`ModelPicker.jsx`: props `{models, value, onChange, kinds=null, compact=false}`; internal state
`q`, `providerFilter`; dropdown button showing current selection label; panel lists options
(filtered case-insensitive across id+label, grouped/sorted free-first then alphabetical);
Free badge on free entries; provider suffix `· provider`; click → onChange(id) + close.
If `kinds` provided, pre-filter to those kinds. All styling matches existing dark theme classes.

- [ ] **Step 4: msw handler** in handlers.js:

```js
http.get('*/api/models', () => HttpResponse.json({
  models: [
    { id: 'poolside/laguna-s-2.1:free', label: 'Laguna S 2.1', provider: 'openrouter',
      kind: 'text', free: true },
    { id: 'nvidia/nemotron-3.5-lightning:free', label: 'Nemotron Lightning', provider: 'openrouter',
      kind: 'text', free: true },
  ],
})),
```

- [ ] **Step 5: GREEN (vitest) + build**
- [ ] **Step 6: Commit** `feat: reusable ModelPicker with search/provider filters/free badge`

---

### Task 6: Settings "Model Assignments" card

**Files:**
- Modify: `money_weaver_frontend/src/components/SettingsPage.jsx` (new card after Model Settings card)
- Modify: `money_weaver_frontend/src/services/api.js` (+getModelAssignments/updateModelAssignments)
- Test: `money_weaver_frontend/src/__tests__/modelAssignments.test.jsx`

- [ ] **Step 1: Failing test** (copy ALL imports + server.use patterns verbatim from
`topicDiscovery.test.jsx` — including how it wraps SettingsPage with auth/query providers):

```jsx
test("assignments card loads and saves", async () => {
  // inside render wrapper used by existing tests:
  server.use(
    http.get('*/api/model-assignments', () =>
      HttpResponse.json({ assignments: { idea: 'x/y' } })),
    http.put('*/api/model-assignments', () => HttpResponse.json({ ok: true })),
  )
  render(<SettingsPage />)  // with the same providers wrapper as existing tests
  expect(await screen.findByText(/model assignments/i)).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: /save assignments/i }))
  await waitFor(() => expect(screen.getByText(/saved/i)).toBeTruthy())
})
```

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement**: five rows — Idea Generation / Script Writing / Prompt Enhance /
Voice (TTS) / Video Generation — each `<ModelPicker>` seeded from GET assignments (voice row
also offers local `auto`; video row also offers `comfy_local` when visible). Local PUT debounced
by explicit Save Assignments button → updateModelAssignments; success/error toast like Save
Preferences card. Kinds restriction per row: idea/script/enhance→['text'], voice_tts→['voice']
(+auto entry), video_gen→['video'] (+comfy_local entry when COMFY_ENABLED — fetch flag from
existing settings/health endpoint if present, else always show comfy_local with "(local)" note).
- [ ] **Step 4: GREEN + build**
- [ ] **Step 5: Commit** `feat: settings model assignments card (5 tasks)`

---

### Task 7: Wizard inline overrides

**Files:**
- Modify: `money_weaver_frontend/src/components/VideoCreationWizard.jsx`
- Test: extend `money_weaver_frontend/src/__tests__/nichePicker.test.jsx` or new `wizardOverrides.test.jsx`

- [ ] **Step 1: Failing tests** — wizard step 1 shows collapsed "Advanced: model overrides"
toggle; expanding reveals two pickers labeled Idea model / Script model pre-seeded via GET
/model-assignments (msw); choosing an override passes `model` field into randomIdea payload
(assert ApiService.randomIdea called with {model: 'chosen/id'} — mock ApiService like existing
tests do).

- [ ] **Step 2: RED → implement → GREEN**
  - Fetch assignments once on wizard mount (react-query or useEffect + ApiService).
  - State: `overrides = {idea: null, script: null}`; picker onChange sets override.
  - Randomize handler: `ApiService.randomIdea(overrides.idea ? {model: overrides.idea} : {})`.
  - Script generation call site (when wired in G2) uses same override pattern.
- [ ] **Step 3: vitest green + build**
- [ ] **Step 4: Commit** `feat: wizard inline model overrides (idea/script)`

---

### Task 8: Voice/video assignment consumption in tasks

**Files:**
- Modify: `money_weaver_backend/src/tasks/video_tasks.py` (generative task video backend branch; assembler voice engine branch reads voice_tts assignment)
- Test: `money_weaver_backend/tests/test_assignment_consumption.py`

- [ ] **Step 1: Failing tests**

```python
def test_generative_uses_fal_when_assigned(monkeypatch, client, auth_headers, db_session, tmp_path):
    """video_gen=fal-ai/... routes through fal_adapter.render, not comfy."""
    from src.tasks import video_tasks as vt
    rendered = {}
    monkeypatch.setenv('COMFY_ENABLED', 'true')
    monkeypatch.setattr(vt, 'resolve_model_for',
                        lambda uid, task: {'video_gen': 'fal-ai/wan-t2v'}[task])
    monkeypatch.setattr(vt.fal_adapter, 'render',
                        lambda ep, args, api_key=None, work_dir=None, timeout_s=600:
                        rendered.update(ep=ep) or str(tmp_path / 'out.mp4'))
    (tmp_path / 'out.mp4').write_bytes(b'MP4')
    monkeypatch.setattr(vt.llm_service, 'generate_script', lambda *a, **k: 'p')
    stored = {}
    fake_storage = mock.Mock()
    fake_storage.put_object = lambda k, d, ct=None: stored.setdefault(k, d)
    monkeypatch.setattr(vt, 'get_storage', lambda: fake_storage)
    # create project/task rows exactly like test_enabled_generative_task_full_path does,
    # invoke task body synchronously, then:
    assert rendered.get('ep') == 'fal-ai/wan-t2v'
    # storage key parity asserted: generative/{pid}/project_{pid}_generative.mp4 present in stored


def test_assembler_voice_tts_auto_keeps_local_chain(monkeypatch, client, auth_headers):
    """voice_tts='auto' (default) must not attempt fal."""
    from src.tasks import video_tasks as vt
    fal_called = {'n': 0}
    monkeypatch.setattr(vt.fal_adapter, 'render',
                        lambda *a, **k: fal_called.__setitem__('n', fal_called['n'] + 1))
    # drive assembler happy path with mocks copied verbatim from
    # tests/test_tasks.py::test_assembler_task_state_transition_pending_to_completed;
    # assert fal_called['n'] == 0
```

- [ ] **Step 2: RED**
- [ ] **Step 3: Implement**
  - Generative enabled branch: `target = resolve_model_for(project.user_id, 'video_gen')`;
    `if target == 'comfy_local':` existing comfy flow unchanged; `elif target.startswith('fal-ai/'):`
    bytes via `fal_adapter.render(target, {prompt, width, height, seed}, api_key=<decrypted fal key via llm_service.api_key_for(user,'fal')>, work_dir=workdir)` then reuse identical write-to-FINAL_DIR + put_object block (extract shared `_store_generative_output(pid, src_path_or_bytes)` helper used by both branches).
  - Assembler voice: `voice_target = resolve_model_for(project.user_id, 'voice_tts')`;
    `if voice_target.startswith('fal-ai/'):` synthesize via fal (arguments {text, voice},
    download wav → write_voice_audio) else existing chain untouched.
  - Import fal_adapter at module top alongside comfy_client.
- [ ] **Step 4: GREEN + full suite**
- [ ] **Step 5: Commit** `feat: voice_tts/video_gen assignments route task execution (comfy_local vs fal)`

---

### Task 9: G1 close-out

- [ ] Full backend suite ≥381+green; coverage ≥55.
- [ ] Frontend vitest green; vite build ok.
- [ ] Live smoke: boot backend+frontend; register probe user; PUT assignments; GET /api/models?kind=voice shows fal entries; voices endpoint still 200.
- [ ] Update `.superpowers/sdd/progress.md` with G1 line; push to contentweaver main.
