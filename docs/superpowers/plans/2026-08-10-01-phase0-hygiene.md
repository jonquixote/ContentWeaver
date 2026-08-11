# Phase 0: Hygiene & Safety — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Get the repo under version control, remove junk/dead code, fix known latent bugs, and make secrets safe — the foundation every later phase builds on.

**Architecture:** Pure cleanup + bugfix. No new features. Establish `.gitignore`, git init, remove debug/dead files, fix the four known frontend bugs (FormData, clipboard, 404 route, sonner mount), move hardcoded secrets to env.

**Tech Stack:** git, npm/pnpm, none new.

## Global Constraints

- Do NOT change runtime behavior of auth or API endpoints in this phase (that's Phase 1)
- Do NOT delete anything still referenced by active code — verify references before deleting
- `.env` files never committed
- SQLite DB (`src/database/app.db`) must remain working after cleanup
- Every task ends with a commit

---

### Task 1: Git init + .gitignore + first commit

**Files:**
- Create: `.gitignore` (repo root)
- Modify: (none)

**Interfaces:**
- Consumes: existing repo layout
- Produces: clean git baseline commit that later phases commit against

- [ ] **Step 1: Verify current state**

Run: `ls -la /Volumes/JOHNNY DISK/MoneyWeaver`
Expected: contains `money_weaver_backend`, `money_weaver_frontend`, `tests`, `video_env`, README.md, summary .md files, `._*` junk

- [ ] **Step 2: Write repo-root `.gitignore`**

Create `/Volumes/JOHNNY DISK/MoneyWeaver/.gitignore`:

```gitignore
# Dependencies
node_modules/

# Builds
dist/
build/

# Python
__pycache__/
*.py[cod]
.venv/
venv/
venv312/
video_env/
*.egg-info/

# Environment / secrets
.env
.env.local
*.pem
litellm_simple.log

# Data / runtime
*.db
*.db-journal
*.rdb
dump.rdb
*.log
work/
uploads/
final/
generated_videos/

# macOS junk
.DS_Store
._*
.AppleDouble

# Editor
.idea/
.vscode/
*.swp

# Test artifacts
.pytest_cache/
htmlcov/
.coverage
```

- [ ] **Step 3: Remove AppleDouble junk files (optional but recommended)**

Run: `find /Volumes/JOHNNY DISK/MoneyWeaver -name '._*' -type f -delete`
Expected: 100+ `._*` files removed. (Safe: these are macOS resource-fork artifacts.)

- [ ] **Step 4: Git init and commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git init -b main
git add .
git commit -m "chore: initial commit of MoneyWeaver codebase"
```

Expected: commit succeeds, `.env`, `venv312/`, `node_modules/`, `video_env/` NOT tracked.

- [ ] **Step 5: Verify**

Run: `git status`
Expected: clean. `git ls-files | grep -c 'venv312'` returns 0. `git ls-files | grep -c 'node_modules'` returns 0.

---

### Task 2: Delete debug/test junk from frontend src

**Files:**
- Delete: `money_weaver_frontend/src/test-api.js`, `endpoint-test.js`, `fetch-test.js`, `module-test.js`, `test-import.js`, `direct-api-test.js`, `test-api-service.js`, `TestComponent.jsx`
- Delete: `money_weaver_frontend/public/api-test.html`, `test-api.html`, `test-video.html`, `simple-video-test.html`
- Delete: `money_weaver_frontend/src/components/SimpleVideoTest.jsx`
- Modify: `money_weaver_frontend/src/App.jsx` (remove route)
- Delete: `money_weaver_frontend/frontend.log`, `frontend_new.log` (if present)

**Interfaces:**
- Consumes: file list above
- Produces: clean src tree; `SimpleVideoTest` route gone

- [ ] **Step 1: Delete files**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_frontend
rm -f src/test-api.js src/endpoint-test.js src/fetch-test.js src/module-test.js src/test-import.js src/direct-api-test.js src/test-api-service.js src/TestComponent.jsx public/api-test.html public/test-api.html public/test-video.html public/simple-video-test.html src/components/SimpleVideoTest.jsx frontend.log frontend_new.log
```

- [ ] **Step 2: Remove SimpleVideoTest route + import from App.jsx**

In `src/App.jsx`, delete the import line `import SimpleVideoTest from './components/SimpleVideoTest'` (line 10) and the route block for `/simple-video-test` (lines 109-116).

- [ ] **Step 3: Verify**

Run: `pnpm lint`
Expected: no lint errors referencing deleted files. (If lint clean, App.jsx is consistent.)

Run: `grep -r "SimpleVideoTest" src/` — no matches.

- [ ] **Step 4: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: remove debug test scripts and dead test components"
```

---

### Task 3: Delete dead backend test scripts and unused code

**Files:**
- Delete (backend root test scripts, keep if actively used — verify each first): `add_default_user.py`, `apply_async_test.py`, `celery_test.py`, `cleanup_databases.py`, `debug_parsing.py`, `direct_task_test.py`, `direct_video_task_test.py`, `fix_videos.py`, `flask_backend_test.py`, `flask_backend_test2.py`, `producer_test.py`, `queue_test.py`, `redis_queue_test.py`, `redis_queue_test2.py`, `redis_test.py`, `simple_celery_test.py`, `simple_test.py`, `test_*.py`
- Delete: `money_weaver_backend/src/routes/audio.py`, `money_weaver_backend/src/routes/model_ids.py` (unregistered/dead blueprints)
- Delete: `money_weaver_backend/src/models/media_asset.py` (never used; single dead import)

**Interfaces:**
- Consumes: report from investigation (these files are dead/debug)
- Produces: clean backend tree

- [ ] **Step 1: Verify each file is not imported**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
grep -rn "media_asset\|audio_bp\|model_ids_bp" src/ | grep -v ".pyc"
```

Expected: only references are in `main.py` imports of media_asset model (remove those too). No imports of audio.py/model_ids.py anywhere.

- [ ] **Step 2: Delete files**

```bash
rm -f add_default_user.py apply_async_test.py celery_test.py cleanup_databases.py debug_parsing.py direct_task_test.py direct_video_task_test.py fix_videos.py flask_backend_test.py flask_backend_test2.py producer_test.py queue_test.py redis_queue_test.py redis_queue_test2.py redis_test.py simple_celery_test.py simple_test.py test_advanced_tts_pytorch.py test_advanced_tts.py test_coherent_narrative.py test_continuous_narrative.py test_improved_assembler.py test_kokoro_customization.py test_kokoro_direct.py test_kokoro_tts.py test_kokoro_voice_patterns.py test_kokoro_voices.py test_problematic_case.py test_script_generation.py test_script_parsing.py test_video_assembler_fixes.py test_video_settings.py src/routes/audio.py src/routes/model_ids.py src/models/media_asset.py
```

- [ ] **Step 3: Remove media_asset import from main.py**

In `src/main.py` line 58, delete `from src.models.media_asset import MediaAsset`.

- [ ] **Step 4: Verify backend still boots**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv312/bin/activate
python -c "from src.main import app; print('OK')"
```

Expected: prints `OK` and table list without traceback.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: delete dead backend debug scripts and unused models/routes"
```

---

### Task 4: Fix frontend known bugs

**Files:**
- Modify: `money_weaver_frontend/src/services/api.js` (FormData handling at lines 28-30)
- Modify: `money_weaver_frontend/src/components/Dashboard.jsx` (clipboard line ~387)
- Modify: `money_weaver_frontend/src/App.jsx` (404 route + mount sonner Toaster)
- Modify: `money_weaver_frontend/src/main.jsx` (mount Toaster)

**Interfaces:**
- Produces: `ApiService.request` correctly handles FormData; `copyText` fixed; unknown routes show 404; toasts appear

- [ ] **Step 1: Fix FormData serialization bug in api.js**

Replace lines 28-30:

```js
if (config.body && typeof config.body === 'object') {
  config.body = JSON.stringify(config.body)
}
```

with:

```js
if (config.body && typeof config.body === 'object' && !(config.body instanceof FormData)) {
  config.body = JSON.stringify(config.body)
}
```

Also remove the stale comment in `cloneVoice` headers (lines 189-191): delete the `headers` block entirely so browser sets multipart boundary.

- [ ] **Step 2: Fix clipboard API**

In `Dashboard.jsx` (~line 387), replace:

```js
navigator.copyText(...)
```

with:

```js
navigator.clipboard.writeText(...)
```

- [ ] **Step 3: Add 404 route + mount Toaster in App.jsx**

Add imports: `import { Toaster } from '@/components/ui/sonner'`. Inside `<Routes>` add catch-all before closing:

```jsx
<Route path="*" element={
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
    <div className="text-center text-white">
      <h1 className="text-4xl font-bold mb-2">404</h1>
      <p className="text-slate-300 mb-4">Page not found</p>
      <a href="/dashboard" className="text-purple-400 hover:text-purple-300">Back to dashboard</a>
    </div>
  </div>
} />
```

Add `<Toaster />` inside `<AuthProvider>` (or right before `</Router>` close).

- [ ] **Step 4: Verify**

Run: `pnpm dev`
Expected: dev server starts, no import errors. Visit `/nonexistent` → 404 page renders.

Run: `pnpm lint`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "fix: FormData upload, clipboard copy, add 404 route and toaster mount"
```

---

### Task 5: Move hardcoded secrets to env

**Files:**
- Modify: `money_weaver_backend/src/main.py` (SECRET_KEY line 23)
- Modify: `money_weaver_backend/src/services/llm_service.py` (line 10)
- Modify: `money_weaver_backend/src/routes/api_keys.py` (line 12)
- Create: `money_weaver_backend/.env.example` (template; `.env` already gitignored)

**Interfaces:**
- Produces: no secrets in code; all config via env with safe dev fallbacks

- [ ] **Step 1: Update main.py SECRET_KEY**

Replace line 23:

```python
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '<redacted-fallback>')
```

with:

```python
app.config['SECRET_KEY'] = os.environ['SECRET_KEY']
```

(Fail fast if missing — no silent fallback in production.)

- [ ] **Step 2: Update llm_service.py and api_keys.py**

Replace `litellm.master_key = "<redacted>"` with:

```python
litellm.master_key = os.getenv('LITELLM_MASTER_KEY', '')
```

- [ ] **Step 3: Create .env.example**

Create `money_weaver_backend/.env.example`:

```
DATABASE_URL=sqlite:////Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend/src/database/app.db
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=change-me-to-a-long-random-string
LITELLM_PROXY_URL=http://localhost:8000
LITELLM_MASTER_KEY=<redacted>
GROQ_API_KEY=
PEXELS_API_KEY=
PIXABAY_API_KEY=
```

- [ ] **Step 4: Verify**

Run: `grep -rn "<redacted>" money_weaver_backend/src/`
Expected: only `.env.example` reference (the dev value), no hardcoded secrets in `.py` files.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "security: move hardcoded secrets to environment variables"
```

---

### Task 6: Verify full app still runs end-to-end

**Files:**
- (none — verification only)

**Interfaces:**
- Consumes: all previous tasks
- Produces: green baseline for Phase 1

- [ ] **Step 1: Start backend**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv312/bin/activate
python src/main.py
```

Expected: starts on 5004, creates tables.

- [ ] **Step 2: Start frontend**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_frontend
pnpm dev
```

Expected: Vite dev server up, dashboard renders, login page loads.

- [ ] **Step 3: Smoke-test register + login**

```bash
curl -s -X POST http://localhost:5004/api/auth/register -H 'Content-Type: application/json' -d '{"email":"smoke@test.com","username":"smoketest","password":"testpass123"}'
```

Expected: 201 with user + token.

- [ ] **Step 4: Commit any stragglers**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: phase 0 baseline verified" || echo "nothing to commit"
```
