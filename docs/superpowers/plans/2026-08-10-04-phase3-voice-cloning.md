# Phase 3: Real Voice Cloning — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the simulated voice cloning (`advanced_tts_service.clone_voice()` ignores reference audio, always uses `af_heart`) with real cloning via **Chatterbox** (Resemble AI, MIT license, 5-second reference cloning). Keep Kokoro-82M as fallback. Store cloned voices per-user.

**Architecture:** Self-hosted Chatterbox inference service (FastAPI, HF `resemble-ai/chatterbox`). Flask backend calls it over HTTP; reference clips stored on MinIO/local (Phase 4 moves to R2). New `Voice` model + `/api/voices` CRUD + `/api/voices/<id>/clone` + `/api/voices/<id>/preview`. Update assembler/generative tasks to accept `voice_id` and select cloned voice. Frontend VoiceCloning page becomes real.

**Tech Stack:** Python 3.12, PyTorch 2.5, Transformers, Chatterbox (github.com/resemble-ai/chatterbox), FastAPI for the TTS microservice, Kokoro fallback. Celery unchanged.

## Global Constraints

- Cloning reference audio: 5-30s, WAV/MP3, 16k+ sample rate
- Each user's voices are owner-scoped (Phase 1 pattern)
- Chatterbox runs on port 8001 (separate from LiteLLM proxy on 8000)
- TTS service startup takes ~30-60s (model load) — expose `/health` with `model_ready` flag; cache model in memory
- Don't download the model at container build — lazy-load on first request
- Fallback: if Chatterbox down, degrade to Kokoro default voice with warning in response
- Voice cloning consent flow: user must confirm they own the voice; store agreement timestamp
- Never store raw reference audio in git

---

### Task 1: Set up Chatterbox TTS microservice

**Files:**
- Create: `money_weaver_backend/tts_service/` package
  - `app.py` (FastAPI)
  - `requirements.txt`
  - `Dockerfile`
  - `.env.example`
- Modify: `money_weaver_backend/requirements.txt` (main service — optional dev dep)

**Interfaces:**
- Produces: HTTP `POST /tts` accepting `{text, reference_audio_url, voice_id}` → returns WAV bytes or `{audio_url}`; `GET /health`

- [ ] **Step 1: Create tts_service dir + files**

```bash
mkdir -p /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend/tts_service
```

- [ ] **Step 2: requirements.txt**

```
fastapi==0.116.1
uvicorn[standard]==0.35.0
torch>=2.2.2
transformers>=4.44.0
torchaudio>=2.2.2
soundfile>=0.12.1
pydub>=0.25.1
requests>=2.31.0
numpy>=1.26.0
```

- [ ] **Step 3: app.py (FastAPI service)**

```python
import io, os, time, tempfile
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import requests, soundfile as sf, numpy as np

app = FastAPI(title="MoneyWeaver TTS")
_model = None
MODEL_ID = os.getenv("CHATTERBOX_MODEL", "resemble-ai/chatterbox")

class TTSRequest(BaseModel):
    text: str
    reference_audio_url: str | None = None
    voice_id: str | None = None
    model: str = "chatterbox"

def load_model():
    global _model
    if _model is not None:
        return _model
    from huggingface_hub import snapshot_download
    from transformers import AutoModel
    # Chatterbox: requires custom load. Use documented approach:
    #   model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True)
    #   model.cuda() if available
    path = snapshot_download(MODEL_ID)
    _model = AutoModel.from_pretrained(path, trust_remote_code=True)
    return _model

@app.get("/health")
def health():
    return {"ok": True, "model_ready": _model is not None}

@app.post("/tts")
def tts(req: TTSRequest):
    try:
        model = load_model()
    except Exception as e:
        raise HTTPException(503, f"Model load failed: {e}")

    # Download reference audio
    if req.reference_audio_url:
        audio, sr = load_audio(req.reference_audio_url)
    else:
        raise HTTPException(400, "reference_audio_url required for cloning")

    # Chatterbox clone + synthesize
    # waveform = model.generate(audio, text)  -- actual API per repo
    # write to buffer
    buf = io.BytesIO()
    # sf.write(buf, waveform, model.sample_rate, format='WAV')
    return Response(buf.getvalue(), media_type="audio/wav")
```

Note: adapt to Chatterbox's exact generate API. Reference: `https://github.com/resemble-ai/chatterbox`.

- [ ] **Step 4: Dockerfile**

```
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
```

- [ ] **Step 5: Verify service boots (CPU)**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend/tts_service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --port 8001 &
curl -s http://localhost:8001/health
```

Expected: `{"ok": true, "model_ready": false}`.

- [ ] **Step 6: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: Chatterbox TTS microservice scaffold"
```

---

### Task 2: Voice model + CRUD routes

**Files:**
- Create: `src/models/voice.py`
- Create: `src/routes/voices.py`
- Modify: `src/main.py` (register model + blueprint)

**Interfaces:**
- Produces: `GET/POST/DELETE /api/voices`, `POST /api/voices/<id>/clone`, `POST /api/voices/<id>/preview`; upload ref audio

- [ ] **Step 1: Voice model**

```python
class Voice(db.Model):
    __tablename__ = 'voices'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    reference_audio_url = db.Column(db.String(500), nullable=False)  # file path or R2 presigned base
    description = db.Column(db.String(300), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    consent_confirmed_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
```

- [ ] **Step 2: Voices routes**

```python
@voices_bp.route('/api/voices', methods=['GET'])
@auth_required
def list_voices():
    voices = Voice.query.filter_by(user_id=g.current_user['id']).all()
    return jsonify([voice_to_dict(v) for v in voices])

@voices_bp.route('/api/voices', methods=['POST'])
@auth_required
def create_voice():
    data = request.form
    file = request.files.get('reference_audio')
    # validate: wav/mp3, 5-30s, <10MB
    # save to uploads/<user_id>/voices/<uuid>.wav
    # require consent checkbox -> consent_confirmed_at = datetime.utcnow()
    ...

@voices_bp.route('/api/voices/<int:voice_id>', methods=['DELETE'])
@auth_required
def delete_voice(voice_id): ...

@voices_bp.route('/api/voices/<int:voice_id>/preview', methods=['POST'])
@auth_required
def preview_voice(voice_id):
    # call TTS service with a fixed phrase
    ...
```

- [ ] **Step 3: Audio validation helper**

```python
import subprocess, json
def validate_audio(path):
    r = subprocess.run(['ffprobe','-v','quiet','-print_format','json','-show_format',path],
                       capture_output=True, text=True)
    fmt = json.loads(r.stdout)['format']
    dur = float(fmt['duration'])
    codec = fmt['format_name']
    assert 5 <= dur <= 30, f"reference must be 5-30s, got {dur:.1f}s"
    # return duration
```

- [ ] **Step 4: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: voice model and owner-scoped CRUD with audio validation"
```

---

### Task 3: Wire real cloning into TTS service calls

**Files:**
- Modify: `src/services/tts_client.py` (new HTTP client) OR extend `src/services/video/advanced_tts_service.py`
- Modify: `src/routes/voice_cloning.py` (replace simulated path)
- Modify: `src/tasks/video_tasks.py` (accept `voice_id`, call TTS client)

**Interfaces:**
- Produces: `/clone-voice` creates a `Voice`, calls TTS to validate + generate a short sample; tasks use cloned voice when `voice_id` provided

- [ ] **Step 1: TTS HTTP client**

```python
# src/services/tts_client.py
import os, requests

TTS_URL = os.getenv('TTS_URL', 'http://localhost:8001')

def tts_health():
    try:
        r = requests.get(f'{TTS_URL}/health', timeout=5)
        return r.json().get('model_ready', False)
    except Exception:
        return False

def synthesize(text, reference_audio_url, voice_id=None):
    r = requests.post(f'{TTS_URL}/tts', json={
        'text': text,
        'reference_audio_url': reference_audio_url,
        'voice_id': voice_id,
    }, timeout=120)
    r.raise_for_status()
    return r.content  # WAV bytes
```

- [ ] **Step 2: Replace clone_voice route**

`POST /api/clone-voice` now: receives voice id + text; calls `synthesize`; stores resulting sample; returns `sample_url`. Do NOT fabricate.

- [ ] **Step 3: Update tasks to accept voice_id**

In `generate_assembler_video_task`/`generate_generative_video_task`, accept `voice_id`. Before TTS:

```python
if voice_id:
    voice = Voice.query.filter_by(id=voice_id, user_id=task.user_id).first()
    if voice:
        audio_bytes = synthesize(segment_text, voice.reference_audio_url)
        # write to work/<scene>/narration.wav
        continue
# else fall back to existing Kokoro/gTTS path
```

Wrap Chatterbox call in try/except; on failure log warning + fallback to Kokoro `af_heart` (existing code path).

- [ ] **Step 4: Verify**

Mock Chatterbox up: `curl -s http://localhost:8001/health` returns `model_ready`. Then in shell test `synthesize`:

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
source venv312/bin/activate
python - <<'EOF'
from src.services.tts_client import tts_health
print("model ready:", tts_health())
EOF
```

- [ ] **Step 5: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: real voice cloning via Chatterbox with kokoro fallback"
```

---

### Task 4: Frontend — make VoiceCloning real

**Files:**
- Modify: `src/components/VoiceCloning.jsx` (remove alert() stub)
- Modify: `src/services/api.js` (voice endpoints)
- Modify: `src/components/VideoCreationWizard.jsx` (voice selector from `/api/voices`)

**Interfaces:**
- Produces: working UI: upload ref audio + name → list voices → play preview → select voice in wizard

- [ ] **Step 1: api.js voice methods**

```js
getVoices: () => api.get('/voices'),
createVoice: (formData) => api.post('/voices', formData),  // FormData (multipart)
previewVoice: (voiceId, text) => api.post(`/voices/${voiceId}/preview`, { text }),
deleteVoice: (voiceId) => api.delete(`/voices/${voiceId}`),
```

- [ ] **Step 2: VoiceCloning component**

Replace `alert(...)` stub with: file input, name field, consent checkbox, upload button → `createVoice(formData)`, grid of created voices with preview button + delete.

- [ ] **Step 3: Wizard voice selector**

On mount fetch `getVoices()`; render `<select>` with "Default (Kokoro)" + cloned voices. Pass `voice_id` to generation payload.

- [ ] **Step 4: Verify + commit**

Manual: upload 10s sample → appears in list → preview plays → select in wizard → generate.

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: real voice cloning UI"
```

---

### Task 5: Phase 3 verification

- [ ] **Step 1: TTS service up + model loads**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend/tts_service
source .venv/bin/activate
uvicorn app:app --port 8001 &
curl -s http://localhost:8001/health
# wait for model_ready true (first request loads)
```

- [ ] **Step 2: End-to-end clone → generate**

Upload ref audio via UI → preview → generate video using cloned voice → verify narration uses reference voice (listening).

- [ ] **Step 3: Fallback test**

Kill TTS service → generate video → should succeed with Kokoro default + warning toast.

- [ ] **Step 4: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "chore: phase 3 voice cloning verified"
```
