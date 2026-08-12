# Phase 3: Real Voice Cloning — Implementation Plan (MOSS-TTS-Nano-ONNX)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the simulated voice cloning (`advanced_tts_service.clone_voice()` ignores reference audio, always uses `af_heart`) with real zero-shot cloning via **MOSS-TTS-Nano-100M-ONNX** (OpenMOSS, Apache-2.0, CPU-only ONNX runtime). Keep Kokoro-82M as fallback. Store cloned voices per-user.

**Why MOSS-TTS-Nano (research-verified on this exact machine):**
- This is an Intel MacBook Pro (i7-9750H, 12 cores, 16GB RAM) — NO CUDA, NO MPS. PyTorch on macOS Intel x86_64 is **capped at 2.2.2** (no torch ≥2.3 wheels).
- Chatterbox (original plan) is DEAD: pins `torch==2.6.0` → cannot install on this Mac.
- OmniVoice is DEAD: pins `torch>=2.4` + CC-BY-NC weights (not commercial-safe) + slow on CPU (RTF 2-6+ vs MOSS ~1.1).
- Pocket-TTS is DEAD: ONNX port (only CPU-viable form) is non-commercial.
- **MOSS-TTS-Nano-ONNX is the only choice that is: torch-free (onnxruntime) + Apache-2.0 + CPU-viable at RTF ~1.1 (measured on this box) + zero-shot 3-10s reference cloning.**
- Benchmark evidence (measured on this box during research): generation RTF ~1.08-1.14 (full decode, 4 threads), ~730MB model download, torch 2.2.2 + onnxruntime 1.20.1 install clean via pip. `--disable-wetext-processing` sidesteps the pynini-on-Intel-Mac wheel problem.

**Architecture:** Self-hosted MOSS-TTS inference service (FastAPI, ONNX CPU, port 8001). Flask backend calls it over HTTP; reference clips stored locally (Phase 4 moves to R2/MinIO). New `Voice` model + `/api/voices` CRUD + `/api/voices/<id>/clone` + `/api/voices/<id>/preview`. Update assembler/generative tasks to accept `voice_id` and select cloned voice. Frontend VoiceCloning page becomes real.

**Tech Stack:** Python 3.12 (dedicated `tts_service/.venv` — MOSS fgcnows pynini wheel issues on 3.13), onnxruntime (torch only for ref resample), MOSS-TTS-Nano-ONNX (huggingface.co/OpenMOSS/MOSS-TTS-Nano or ModelScope mirror `openmoss/MOSS-TTS-Nano`), FastAPI for the TTS microservice, Kokoro fallback. Celery unchanged. **Do NOT touch the main `venv` (Python 3.13).**

## Global Constraints

- Cloning reference audio: 3-10s (5-20s ok), WAV/MP3, 16k+ sample rate
- Each user's voices are owner-scoped (Phase 1 pattern)
- MOSS TTS service runs on port 8001 (separate from LiteLLM proxy on 8000)
- TTS service startup takes ~10-60s (model load) — expose `/health` with `model_ready` flag; cache model in memory
- Don't download the model at container build — lazy-load on first request
- Fallback: if MOSS TTS down, degrade to Kokoro default voice with warning in response
- Voice cloning consent flow: user must confirm they own the voice; store agreement timestamp
- Never store raw reference audio in git
- TTS service runs with its own venv at `tts_service/.venv` — INSTALL deps there, never in main `venv`
- Install MOSS from pip with `--no-deps`, then manually pin deps (torch==2.2.2, torchaudio==2.2.2, onnxruntime, soundfile, numpy) — see Task 1 Step 2
- Use `--disable-wetext-processing` flag (or norm env) to skip pynini/WeTextProcessing (no Intel-Mac wheel)
- Output is generated via `infer` with `--backend onnx`; sample rate 24000 to match Kokoro pipeline

---

### Task 1: Set up MOSS-TTS inference microservice

**Files:**
- Create: `money_weaver_backend/tts_service/` package
  - `app.py` (FastAPI)
  - `requirements.txt`
  - `Dockerfile`
  - `.env.example`
- Modify: `money_weaver_backend/requirements.txt` (main service — dev dep comment only)

**Interfaces:**
- Produces: HTTP `POST /tts` accepting `{text, reference_audio_url, voice_id}` → returns WAV bytes; `GET /health` returns `{ok, model_ready}`

- [ ] **Step 1: Create tts_service dir + files**

```bash
mkdir -p /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend/tts_service
```

- [ ] **Step 2: requirements.txt (Python 3.12, Intel-Mac-safe pins)**

```
# Run in tts_service/.venv (python 3.12). NEVER install into main venv.
fastapi==0.116.1
uvicorn[standard]==0.35.0
# torch capped at 2.2.2 for macOS Intel x86_64 (no wheels >= 2.3)
torch==2.2.2
torchaudio==2.2.2
onnxruntime>=1.20.0
soundfile>=0.12.1
numpy>=1.26.0,<2.0
requests>=2.31.0
# MOSS-TTS-Nano installed via --no-deps + pip install -e (or git clone)
# python-multipart for uploads if serving ref directly
```

Remove the vendored `infer_onnx.py`/`onnx_tts_runtime.py` CLI dependency on pynini by using the repo's `--disable-wetext-processing`/`--backend onnx` path.

- [ ] **Step 3: app.py (FastAPI service using MOSS onnx runtime)**

```python
import io, os, time, tempfile, subprocess
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

app = FastAPI(title="MoneyWeaver TTS (MOSS-TTS-Nano-ONNX)")
_model = None
_repo_dir = os.getenv("MOSS_TTS_REPO", os.path.join(os.path.dirname(__file__), "MOSS-TTS-Nano"))

class TTSRequest(BaseModel):
    text: str
    reference_audio_url: str | None = None  # local path or http url
    voice_id: str | None = None
    model: str = "moss-nano"

def load_model():
    global _model
    if _model is not None:
        return _model
    # MOSS-TTS-Nano onnx inference: use repo's onnx_tts_runtime / infer_onnx.py
    # Reference docs: github.com/OpenMOSS/MOSS-TTS-Nano
    # CLI: python infer_onnx.py --prompt-audio-path ref.wav --text "..." \
    #      --backend onnx --disable-wetext-processing
    # For in-process inference, build MOSSAccentONNX runtime from
    # moss_tts.onnx_tts_runtime (or call the ONNX session directly) and cache it.
    # Implementation note: adapt to the repo's current onnx runtime API.
    _model = True  # placeholder until onnx runtime wired
    return _model

@app.get("/health")
def health():
    return {"ok": True, "model_ready": _model is not None}

@app.post("/tts")
def tts(req: TTSRequest):
    try:
        load_model()
    except Exception as e:
        raise HTTPException(503, f"Model load failed: {e}")
    if not req.reference_audio_url:
        raise HTTPException(400, "reference_audio_url required for cloning")
    if not req.text.strip():
        raise HTTPException(400, "text required")
    # download ref audio to temp wav (if http), run onnx inference to wav bytes
    # waveform = run_inference(prompt_audio, text)  # 24kHz mono
    # buf = io.BytesIO(); sf.write(buf, waveform, 24000, format='WAV')
    # return Response(buf.getvalue(), media_type="audio/wav")
```

**Task 1 implementation note:** The exact MOSS ONNX runtime API must be read from the cloned repo at build time (`MOSS-TTS-Nano/onnx_tts_runtime.py`). Implementer must (a) clone/download the repo into `tts_service/`, (b) wire `load_model()` to the real onnx runtime, (c) actually write WAV bytes in `/tts`. If MOSS is not yet cloned, download ONNX weights (~730MB) on first `/tts` request (lazy).

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
python3.12 -m venv .venv
source .venv/bin/activate
pip install --no-cache-dir -r requirements.txt
uvicorn app:app --port 8001 &
curl -s http://localhost:8001/health
```

Expected: `{"ok": true, "model_ready": false}` (model lazy-loads on first request).

- [ ] **Step 6: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: MOSS-TTS microservice scaffold"
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
    reference_audio_url = db.Column(db.String(500), nullable=False)  # local file path
    description = db.Column(db.String(300), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    consent_confirmed_at = db.Column(db.DateTime, nullable=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
```

- [ ] **Step 2: Voices routes**

```python
@voices_bp.route('/voices', methods=['GET'])
@auth_required
def list_voices():
    voices = Voice.query.filter_by(user_id=g.current_user['id']).all()
    return jsonify([voice_to_dict(v) for v in voices])

@voices_bp.route('/voices', methods=['POST'])
@auth_required
def create_voice():
    # multipart: name, reference_audio (5-30s wav/mp3), description, consent checkbox
    # validate audio; require consent_confirmed_at = utcnow(); save uploads/<user_id>/voices/<uuid>.wav
    ...

@voices_bp.route('/voices/<int:voice_id>', methods=['DELETE'])
@auth_required
def delete_voice(voice_id):
    # owner check, delete row + ref file, 404 if not found, 403 cross-user
    ...

@voices_bp.route('/voices/<int:voice_id>/preview', methods=['POST'])
@auth_required
def preview_voice(voice_id):
    # owner check; call TTS service with fixed phrase; store sample; return sample_url
    ...
```

Register `voices_bp` with `url_prefix='/api'`, add `Voice` to `main.py` model imports + `db.create_all()`.

- [ ] **Step 3: Audio validation helper**

```python
import subprocess, json
def validate_audio(path):
    r = subprocess.run(['ffprobe','-v','quiet','-print_format','json','-show_format',path],
                       capture_output=True, text=True)
    fmt = json.loads(r.stdout)['format']
    dur = float(fmt['duration'])
    assert 5 <= dur <= 30, f"reference must be 5-30s, got {dur:.1f}s"
    return dur
```

(`ffprobe` confirmed at `/usr/local/bin/ffprobe`.)

- [ ] **Step 4: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: voice model and owner-scoped CRUD with audio validation"
```

---

### Task 3: Wire real cloning into TTS service calls

**Files:**
- Create: `src/services/tts_client.py` (HTTP client for TTS microservice)
- Modify: `src/routes/voice_cloning.py` (keep legacy route working OR route to voices flow)
- Modify: `src/tasks/video_tasks.py` (accept `voice_id`, call TTS client; generate_assembler_video_task + generate_generative_video_task signatures)

**Interfaces:**
- Produces: voice flow uses TTS service; `generate_assembler_video_task(project_id, prompt, ..., voice_id=None)`; fallback to Kokoro when TTS down or voice_id absent

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

def synthesize(text, reference_audio_url, voice_id=None, timeout=300):
    r = requests.post(f'{TTS_URL}/tts', json={
        'text': text,
        'reference_audio_url': reference_audio_url,
        'voice_id': voice_id,
    }, timeout=timeout)
    r.raise_for_status()
    return r.content  # WAV bytes
```

- [ ] **Step 2: Update assembler/generative tasks to accept voice_id**

In `generate_assembler_video_task(..., voice_id=None)` / `generate_generative_video_task(..., voice_id=None)`:

```python
if voice_id:
    voice = Voice.query.filter_by(id=voice_id, user_id=user_id).first()
    if voice:
        try:
            wav = synthesize(voiceover_text, voice.reference_audio_url)
            # write to work/<scene>/narration.wav (24kHz) and use it
        except Exception as e:
            print(f"Chatterbox TTS unavailable, falling back to Kokoro: {e}")
            audio_file = advanced_tts_service.generate_tts(voiceover_text, model_type="kokoro", voice=voice or 'af_heart')
# else: existing Kokoro path
```

`POST /api/generate/assembler` and `/generate/generative` accept optional `voice_id` in payload and pass through to the task.

- [ ] **Step 3: Verify — smoke the TTS client**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver/money_weaver_backend
./venv/bin/python - <<'EOF'
from src.services.tts_client import tts_health
print("model ready:", tts_health())
EOF
```

(Use `./venv/bin/python` — `venv312` is a dead symlink. Expected: False if TTS service down; True when up and loaded.)

- [ ] **Step 4: Commit**

```bash
cd /Volumes/JOHNNY DISK/MoneyWeaver
git add -A
git commit -m "feat: real voice cloning via MOSS-TTS with Kokoro fallback"
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

(The existing `getAvailableVoices()`/`cloneVoice()` can be kept or refactored; the new `/voices` endpoints are the source of truth.)

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

---

## Research Sources (decision record)

- MOSS-TTS-Nano repo + HF: github.com/OpenMOSS/MOSS-TTS-Nano — Apache-2.0, ONNX runtime path, `--disable-wetext-processing` (Issue #6 documents pynini workaround), ModelScope mirror `openmoss/MOSS-TTS-Nano`.
- MOSS ONNX benchmark on this box (measured, research subagent): RTF ~1.08–1.14 full-decode 4 threads; streaming ~1.5; install: torch 2.2.2 + onnxruntime 1.20.1 pip-clean; models 728MB total.
- PyTorch macOS Intel cap: torch 2.2.2 last x86_64 build (pytorch.org blog + dev-discuss).
- Chatterbox eliminated: torch==2.6.0 pin (no Intel wheel) + baked-in PerTh watermark + unverified "3x realtime" CPU claim.
- OmniVoice eliminated: pyproject pins torch>=2.4 + CC-BY-NC weights + Higgs/Boson 100k-user cap + CPU RTF 2-6x slower than MOSS.
- Pocket-TTS eliminated: ONNX (only CPU path) declared non-commercial.

---
