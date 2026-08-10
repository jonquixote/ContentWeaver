# Phase 2: Core Product Features — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the video-generation product actually usable: format presets (aspect ratio + duration + resolution presets), bolded caption support in generated videos, reusable templates, thumbnail generation, and a working project detail / task status view. Fix the confirmed task-creation bugs.

**Architecture:** Backend-first. Extend `Task`, `Project` models + `video_settings.py`. Add preset lookup endpoints, template CRUD, thumbnail generation in the assembly service, and an SSE/JSON status endpoint with real progress. Frontend: rebuild `VideoCreationWizard` to consume presets, wire Dashboard to real project data (remove mock), add a project detail page with video player + task progress.

**Tech Stack:** Flask, FFmpeg (already installed), MoviePy 2.x (new dep, optional), existing Celery pipeline. No new infra.

## Global Constraints

- All endpoints auth-required (from Phase 1) and owner-scoped
- Default model `groq/llama-3.3-70b-versatile` via LiteLLM; structured output via `response_format` where supported
- Presets come from DB table seeded on startup; cache in memory
- Bolded captions: rendered as `.srt`-compatible ASS/filter drawtext with bold styling — test output visually with ffmpeg thumbnail
- Keep `work/`, `final/` dirs per-project under `uploads/<project_id>/`
- Every task ends with a commit

---

### Task 1: Seed + serve format presets

**Files:**
- Create: `money_weaver_backend/src/models/preset.py`
- Modify: `src/main.py` (register model, seed)
- Create: `src/routes/presets.py`
- Modify: `src/routes/__init__.py` or blueprint registration

**Interfaces:**
- Produces: `GET /api/presets` returns list of format presets

- [ ] **Step 1: Preset model**

```python
class FormatPreset(db.Model):
    __tablename__ = 'format_presets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    platform = db.Column(db.String(50), nullable=False)      # youtube/shorts/tiktok/reels/custom
    width = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    fps = db.Column(db.Integer, nullable=False, default=30)
    duration_min = db.Column(db.Integer, nullable=False, default=15)
    duration_max = db.Column(db.Integer, nullable=False, default=120)
    is_default = db.Column(db.Boolean, default=False)
```

- [ ] **Step 2: Seed defaults on app start**

In `create_app()`, after `db.create_all()`:

```python
from src.models.preset import FormatPreset
SEED_PRESETS = [
    ('YouTube Landscape', 'youtube', 1920, 1080, 30, 60, 600, True),
    ('YouTube Shorts', 'shorts', 1080, 1920, 30, 15, 60, False),
    ('TikTok', 'tiktok', 1080, 1920, 30, 15, 60, False),
    ('Instagram Reels', 'reels', 1080, 1920, 30, 15, 60, False),
    ('Instagram Square', 'instagram', 1080, 1080, 30, 15, 60, False),
    ('Twitter/X', 'twitter', 1280, 720, 30, 15, 60, False),
]
if FormatPreset.query.count() == 0:
    for name, platform, w, h, fps, dmin, dmax, is_def in SEED_PRESETS:
        db.session.add(FormatPreset(name=name, platform=platform, width=w, height=h,
                                    fps=fps, duration_min=dmin, duration_max=dmax, is_default=is_def))
    db.session.commit()
```

- [ ] **Step 3: Presets route**

`src/routes/presets.py`:

```python
from flask import Blueprint, jsonify
from src.models.preset import FormatPreset

presets_bp = Blueprint('presets', __name__)

@presets_bp.route('/api/presets', methods=['GET'])
def list_presets():
    presets = FormatPreset.query.order_by(FormatPreset.is_default.desc()).all()
    return jsonify([{'id': p.id, 'name': p.name, 'platform': p.platform,
                     'width': p.width, 'height': p.height, 'fps': p.fps,
                     'duration_min': p.duration_min, 'duration_max': p.duration_max,
                     'is_default': p.is_default} for p in presets])
```

Register `presets_bp` in `main.py`.

- [ ] **Step 4: Verify**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv312/bin/activate
python src/main.py &
TOKEN=$(curl -s -X POST http://localhost:5004/api/auth/login -H 'Content-Type: application/json' -d '{"email":"smoke@test.com","password":"testpass123"}' | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s http://localhost:5004/api/presets -H "Authorization: Bearer $TOKEN"
```

Expected: JSON array of 6 presets.

- [ ] **Step 5: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: format presets with seed data and API"
```

---

### Task 2: Fix task creation bugs in generation routes

**Files:**
- Modify: `src/routes/video_generation.py`
- Modify: `src/routes/voice_cloning.py`

**Interfaces:**
- Produces: tasks always created with `db.session.add(task)` + `user_id` + `project_id` set; status codes sane

- [ ] **Step 1: Fix missing `db.session.add(task)` in assembler/generative**

In `/generate/assembler` and `/generate/generative`, ensure:

```python
task = Task(...)
db.session.add(task)
db.session.commit()
```

Replace any `status=190` with valid enum (use `PENDING`/`QUEUED` = 0 or defined constant). Add `user_id=g.current_user['id']` and `project_id` from request (create project if absent).

- [ ] **Step 2: Verify task creation end-to-end**

```bash
TOKEN=$(...)
curl -s -X POST http://localhost:5004/api/generate/assembler \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"script":"Title: Test\nFull Narrative: A finance tip.","duration":15}'
```

Then check the returned `task_id` exists:

```bash
curl -s http://localhost:5004/api/tasks/<task_id> -H "Authorization: Bearer $TOKEN"
```

- [ ] **Step 3: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "fix: create tasks with user/project association in generation routes"
```

---

### Task 3: Bolded caption rendering in assembly

**Files:**
- Modify: `src/services/video/assembly_service.py`
- Modify: `src/services/video/video_settings.py` (caption style config)

**Interfaces:**
- Produces: caption `.srt` with bold markup converted to ASS bold styling; ffmpeg filter renders bold text

- [ ] **Step 1: Add bold-caption config**

In `video_settings.py` add:

```python
CAPTION_FONT = os.getenv('CAPTION_FONT', 'Arial')
CAPTION_FONT_SIZE = int(os.getenv('CAPTION_FONT_SIZE', '28'))
CAPTION_COLOR = os.getenv('CAPTION_COLOR', 'white')
CAPTION_BORDER = int(os.getenv('CAPTION_BORDER', '2'))
```

- [ ] **Step 2: Convert bold markup to ASS**

Add function in `assembly_service.py`:

```python
def build_caption_style(segments, width, height):
    """Segments: list of {text, start, end}. Return .ass subtitle file path."""
    # Map **bold** markers in text to {\b1}...{\b0} inside ASS
    # Write .ass file to work_dir with PlayResX/PlayResY = width/height
```

Use `re.sub(r'\*\*(.+?)\*\*', r'{\\b1}\1{\\b0}', text)` to translate Markdown-style bold into ASS bold.

- [ ] **Step 3: Use ass file in ffmpeg drawtext/subtitles filter**

Change the ffmpeg subtitle filter to:

```
-vf "subtitles=captions.ass:fontsdir=..."
```

- [ ] **Step 4: Test with a sample**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv312/bin/activate
python - <<'EOF'
from src.services.video.assembly_service import build_caption_style
path = build_caption_style([
    {'text': '**Buy low** and sell high', 'start': 0, 'end': 3},
    {'text': 'Compound **interest** is powerful', 'start': 3, 'end': 6},
], 1920, 1080)
print(path)
# Verify file contains {\b1}Buy low{\b0}
EOF
```

- [ ] **Step 5: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: bold caption rendering in video assembly"
```

---

### Task 4: Templates CRUD

**Files:**
- Create: `src/models/template.py`
- Create: `src/routes/templates.py`
- Modify: `src/main.py` (register blueprint)

**Interfaces:**
- Produces: `GET/POST/PUT/DELETE /api/templates`, owner-scoped; used by wizard "load template"

- [ ] **Step 1: Template model**

```python
class VideoTemplate(db.Model):
    __tablename__ = 'video_templates'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    config = db.Column(db.JSON, nullable=False)   # preset id, voice, duration, caption style
    is_public = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: Templates routes**

CRUD endpoints all scoped with `user_id=g.current_user['id']`. Public templates queryable by all users (`is_public=True`).

- [ ] **Step 3: Verify + commit**

```bash
curl -s -X POST http://localhost:5004/api/templates -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"My Shorts","config":{"preset_id":2,"voice":"af_heart","duration":20}}'
```

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: video template CRUD"
```

---

### Task 5: Thumbnail generation

**Files:**
- Modify: `src/services/video/assembly_service.py`
- Modify: `src/models/task.py` (add `thumbnail_path`)

**Interfaces:**
- Produces: `.jpg` thumbnail from first non-black frame after assembly; stored in `uploads/<project_id>/thumb.jpg`

- [ ] **Step 1: Extract thumbnail**

```python
def generate_thumbnail(video_path, output_dir, width=1280):
    # ffmpeg -ss 2 -i video.mp4 -frames:v 1 -q:v 2 thumb.jpg
    # Skip first 2s (likely black intro)
```

- [ ] **Step 2: Wire into assembler task**

Call after final assembly; save `task.thumbnail_path`; include URL in task status JSON.

- [ ] **Step 3: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: generate video thumbnails after assembly"
```

---

### Task 6: Real task status endpoint + frontend wiring

**Files:**
- Modify: `src/routes/task.py` (status + progress)
- Create: `money_weaver_frontend/src/hooks/useTaskStatus.js`
- Modify: `src/components/VideoCreationWizard.jsx`, `src/components/Dashboard.jsx`

**Interfaces:**
- Produces: task status returns `progress` (0-100), `status_label`, `video_url`, `thumbnail_url`; Dashboard shows real project list; wizard polls status during generation

- [ ] **Step 1: Task status response shape**

Update `/api/tasks/<id>/status` to return:

```json
{"id": 1, "status": "processing", "progress": 42, "message": "Rendering scene 3/5", "video_url": null, "thumbnail_url": null, "error": null}
```

Add `progress` column to `Task` (default 0). Update `generate_*_task` to call `update_progress(task, pct, msg)`.

- [ ] **Step 2: useTaskStatus hook**

```js
// src/hooks/useTaskStatus.js
import { useState, useEffect, useCallback } from 'react'
import api from '@/services/api'

export function useTaskStatus(taskId, enabled = false, intervalMs = 3000) {
  const [status, setStatus] = useState(null)
  useEffect(() => {
    if (!taskId || !enabled) return
    const timer = setInterval(async () => {
      const res = await api.get(`/tasks/${taskId}/status`)
      setStatus(res.data)
      if (res.data.status === 'completed' || res.data.status === 'failed') {
        clearInterval(timer)
      }
    }, intervalMs)
    return () => clearInterval(timer)
  }, [taskId, enabled, intervalMs])
  return { status, setStatus }
}
```

- [ ] **Step 3: Replace mock data in Dashboard**

Remove hardcoded stats/projects; fetch from `/projects` with loading/error states and sonner toasts.

- [ ] **Step 4: Wizard polls status**

After task created, call `useTaskStatus(taskId, enabled)` and render progress bar with `message`.

- [ ] **Step 5: Verify + commit**

Manual: create video in wizard → progress bar updates → link appears. 

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: real task status polling and dashboard project data"
```

---

### Task 7: Project detail page with player

**Files:**
- Create: `money_weaver_frontend/src/pages/ProjectDetail.jsx`
- Modify: `src/App.jsx` (route `/projects/:id`)

**Interfaces:**
- Produces: project page shows script, status, video `<video>` player, thumbnail, re-generate button

- [ ] **Step 1: Build ProjectDetail page**

Fetch `/projects/<id>` + `/tasks?project_id=<id>`. Render video with `<video controls src={task.video_url}>`, script preview, progress.

- [ ] **Step 2: Add route**

```jsx
<Route path="/projects/:id" element={<ProjectDetail />} />
```

- [ ] **Step 3: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: project detail page with video player"
```

---

### Task 8: Phase 2 verification

- [ ] **Step 1: Full smoke test**

Register → create project → generate video from preset → poll status → completed → open player → thumbnail exists.

- [ ] **Step 2: lint frontend**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_frontend
pnpm lint
```

- [ ] **Step 3: Commit final**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: phase 2 core features verified"
```
