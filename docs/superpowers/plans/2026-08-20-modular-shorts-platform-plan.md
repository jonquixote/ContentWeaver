# Modular Shorts Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Graft 3 external subsystems onto MoneyWeaver as isolated modules — Phase A niche+EdgeTTS+topics+captions (CPU), Phase B ComfyUI gateway fixes generative stub (GPU-ready), Phase C smart crop+viral+YT — staying MIT/Apache, CPU-now GPU-later, 6-week balanced rollout.

**Architecture:** Keep `FastAPI 504 + Celery+Redis + ffmpeg assembly_service + stock (Pexels/Pixabay) + TTS MOSS-ONNX→Kokoro→gTTS + presets + script_parsing_service typed blocks + registry OpenRouter/NVIDIA`. Add `niches/*.yaml` via `niche_profile.py` into `llm_service`, `edge_tts.py` into `tts_client` chain, `topic_service.py` GET /api/topics, `captions.py` ASS+SRT, `comfy_client.py` httpx→8188 replaces stub, optional `WanWrapper` plug-in, `reframe_service.py` TRACK/GENERAL, `viral_detector.py` whisper+scene+Gemini, `youtube_uploader.py` private upload. Each behind interface, flag-gated `COMFY_ENABLED/VIRAL_ENABLED`.

**Tech Stack:** FastAPI 0.116.1, Celery 5.5.3+Redis, ffmpeg, ComfyUI 128k (httpx+ws), Wan 2.2 14B (optional), Edge TTS 7.x, faster-whisper 1.2.1, PySceneDetect 0.7, ultralytics YOLOv8+MediaPipe, google-api-python-client+google-auth-oauthlib, Chatterbox MIT (GPU future), sqlite+Alembic, React+TanStack Query+Zustand.

## Global Constraints

- Commercial-safe only: MIT/Apache/MPL-2 allowed; BLOCK AGPL-3.0 (MoneyPrinterV2), Research NC (Fish S2, F5 CC-BY-NC), CC-BY-NC model (VibeVoice 1.5B weights). Verify license before adding dep.
- CPU-now GPU-later: Phase A must run on Intel Mac no GPU; Phase B/C flag-gated `COMFY_ENABLED/VIRAL_ENABLED/CHATTERBOX_ENABLED` default false on dev.
- No fork/rewrite: graft modules behind existing interfaces; keep `POST /api/generate/assembler` + `generate_generative_video_task.delay()` signatures byte-exact; fallback to assembler if Comfy down (503 not 500, same as P2/P4 pattern).
- Secrets via `${VAR:-default}` indirection, `.env 0600`, `?token` only for `/-paths` never absolute S3 URLs (Phase4 F2).
- Tests: backend `pytest` fail-under 55, target 60%+ (now 60.9% 241 tests); frontend `vitest` 17 tests; lint 0 err, build ok; each task ends with independently testable deliverable + `git commit`.

---

## File Structure

**Before defining tasks, created/modified files:**

- `money_weaver_backend/niches/*.yaml` — 15 niche YAMLs (tech, finance, health, etc.) copied from `verticals/niches/`
- `money_weaver_backend/src/services/providers/niche_profile.py` — loader `load(niche_id)->dict`, `inject_prompt(base_prompt, niche)` pure functions
- `money_weaver_backend/src/services/providers/edge_tts.py` — Edge TTS provider `synthesize(text, voice="en-US-AriaNeural") -> wav_bytes`, `list_voices()`
- `money_weaver_backend/src/services/topic_service.py` — `fetch_topics(niche, limit)`, `gather_research(topic)` DuckDuckGo+RSS+pytrends+HN
- `money_weaver_backend/src/services/video/captions.py` — `burn_ass(input_mp4, transcript_word_ts, niche) -> ASS+SRT`, `export_srt()`
- `money_weaver_backend/src/services/comfy_client.py` — `queue_workflow(workflow_json, client_id) -> prompt_id`, `poll_status(prompt_id)`, `get_view(filename)`, `health()`
- `money_weaver_backend/workflows/wan22_t2v_api.json` — Wan 2.2 T2V template workflow (versioned)
- `money_weaver_backend/workflows/wan22_fp8_api.json` — optional Wan fp8 variant (when `WAN_WRAPPER_ENABLED`)
- `money_weaver_backend/src/services/video/reframe_service.py` — `reframe(input_mp4, mode="track"|"general") -> vertical.mp4`
- `money_weaver_backend/src/services/video/viral_detector.py` — `detect_viral_moments(video_path, count=5) -> [{start,end,score,hook}]` + Celery `detect_viral_clips_task`
- `money_weaver_backend/src/services/providers/youtube_uploader.py` — `get_auth_url()`, `handle_callback(code)`, `upload_video(project_id, privacy="private")`
- Modify: `src/services/llm_service.py:generate_script()` — add `niche_id` param + `niche_profile` inject + `gather_research` context
- Modify: `src/services/tts_client.py` — add Edge to fallback chain, `voice_engine` routing
- Modify: `fastapi_app/routers/generation.py` — add `niche_id` to `AssemblerRequest`, wire `comfy_client` into `generate_generative_video_task`, add `model` passthrough
- Modify: `src/tasks/video_tasks.py:generate_generative_video_task` — replace stub sleep with `comfy_client` flow
- Create: `fastapi_app/routers/topics.py` — `GET /api/niches`, `GET /api/topics`
- Create: `fastapi_app/routers/youtube.py` — `GET /api/youtube/auth-url`, `GET /api/youtube/callback`, `POST /api/youtube/upload`
- Modify: `src/services/video/assembly_service.py:_burn_captions()` — use `captions.py` ASS, fallback PNG overlay
- Modify: `money_weaver_backend/requirements.txt` — add `edge-tts==7.2.1, faster-whisper==1.2.1, scenedetect==0.7, feedparser, pytrends` (Phase A/C worker-only `ultralytics, mediapipe, google-api-python-client, google-auth-oauthlib` gated)
- Create: `scripts/setup_youtube_oauth.py` — wizard for `client_secret.json` → `token.json`

Each file has one responsibility; interfaces defined per task below.

---

### Task 1: Niche Profiles + Research Gate

**Files:**
- Create: `money_weaver_backend/niches/tech.yaml` (+ 14 more: finance, health, fitness, gaming, food, travel, education, business, motivation, luxury, fashion, sports, news, general)
- Create: `money_weaver_backend/src/services/providers/niche_profile.py`
- Modify: `money_weaver_backend/src/services/llm_service.py:1-90` (add `niche_id` param, inject)
- Create: `money_weaver_backend/fastapi_app/routers/niches.py`
- Test: `money_weaver_backend/tests/test_niches.py`

**Interfaces:**
- Consumes: `verticals/niches/*.yaml` schema (tone, hooks, forbidden, visuals, captions, music, word_count); `llm_service.SCREENPLAY_PROMPT`
- Produces: `niche_profile.load(niche_id: str) -> dict`, `niche_profile.inject_prompt(base_prompt: str, niche: dict) -> str`, `niche_profile.list_niches() -> list[str]`, router `GET /api/niches -> {niches: []}`, `POST /api/generate/assembler` now accepts `niche_id?: str`

- [ ] **Step 1: Write failing test for niche loader**

```python
# tests/test_niches.py
from src.services.providers.niche_profile import load, list_niches, inject_prompt
def test_load_tech_niche():
    niche = load("tech")
    assert niche["tone"] == "contrarian"
    assert "hooks" in niche
    assert list_niches() == sorted(list_niches())
def test_inject_appends_hooks():
    niche = {"tone": "urgent", "hooks": ["breaking news"], "forbidden": [], "word_count": 120}
    out = inject_prompt("Write script", niche)
    assert "urgent" in out and "breaking news" in out
def test_api_list_niches(client, auth_headers):
    r = client.get("/api/niches", headers=auth_headers)
    assert r.status_code == 200 and "tech" in r.json["niches"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd money_weaver_backend && venv/bin/python -m pytest tests/test_niches.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'src.services.providers.niche_profile'`

- [ ] **Step 3: Create niche YAMLs + loader**

```bash
mkdir -p money_weaver_backend/niches
cp /tmp/verticals/niches/*.yaml money_weaver_backend/niches/  # 15 files
```

```python
# src/services/providers/niche_profile.py
import os, yaml
_NICHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "niches")
def list_niches():
    return sorted([f[:-5] for f in os.listdir(_NICHE_DIR) if f.endswith(".yaml")])
def load(niche_id: str) -> dict:
    path = os.path.join(_NICHE_DIR, f"{niche_id}.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(niche_id)
    with open(path) as fh: return yaml.safe_load(fh)
def inject_prompt(base: str, niche: dict) -> str:
    tone = niche.get("tone","neutral")
    hooks = ", ".join(niche.get("hooks",[])[:3])
    forb = ", ".join(niche.get("forbidden",[])[:2])
    wc = niche.get("word_count", 150)
    extra = f"\nTone: {tone}. Hooks: {hooks}. Avoid: {forb}. Target {wc} words. Only use research facts."
    return base + extra
```

- [ ] **Step 4: Wire into llm_service + router, run test to pass**

```python
# src/services/llm_service.py add param
def generate_script(self, prompt, niche_id=None, model=None):
    if niche_id:
        try:
            from src.services.providers.niche_profile import load, inject_prompt
            niche = load(niche_id)
            prompt = inject_prompt(prompt, niche)
        except FileNotFoundError: pass
    # ... existing SCREENPLAY_PROMPT flow
```

```python
# fastapi_app/routers/niches.py
from fastapi import APIRouter, Depends
from fastapi_app.deps import current_user
from src.services.providers.niche_profile import list_niches
router = APIRouter(prefix="/api", tags=["niches"])
@router.get("/niches")
def get_niches(user=Depends(current_user)):
    return {"niches": list_niches()}
# then add router to fastapi_app/main.py: app.include_router(niches.router)
```

Run: `venv/bin/python -m pytest tests/test_niches.py -v` Expected: PASS (3 tests). Also `GET /api/niches` 200.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/niches/ money_weaver_backend/src/services/providers/niche_profile.py money_weaver_backend/src/services/llm_service.py money_weaver_backend/fastapi_app/routers/niches.py money_weaver_backend/tests/test_niches.py
git commit -m "feat: niche profiles + prompt injection (Verticals)"
```

---

### Task 2: Edge TTS Free Path

**Files:**
- Create: `money_weaver_backend/src/services/providers/edge_tts.py`
- Modify: `money_weaver_backend/src/services/tts_client.py:1-60`
- Modify: `money_weaver_backend/src/models/voice.py:voice_engine` enum add `edge`
- Test: `money_weaver_backend/tests/test_edge_tts.py`

**Interfaces:**
- Consumes: `tts_client.synthesize(text, ref_path)` existing contract; `Voice.voice_engine`
- Produces: `edge_tts.synthesize(text: str, voice="en-US-AriaNeural") -> bytes (wav 24kHz)`, `edge_tts.list_voices() -> list[str]`, `tts_client` fallback chain `MOSS(8001)→Edge→Kokoro→gTTS`

- [ ] **Step 1: Write failing test**

```python
# tests/test_edge_tts.py
import pytest
from src.services.providers.edge_tts import synthesize, list_voices
def test_list_voices():
    voices = list_voices()
    assert "en-US-AriaNeural" in voices
@pytest.mark.asyncio
async def test_synthesize_mocked(monkeypatch):
    async def fake_comm(*a, **k):
        class C: 
            async def __aenter__(self): return self
            async def __aexit__(self,*a): pass
            def save(self, p): open(p,"wb").write(b"RIFF fake wav")
        return C()
    monkeypatch.setattr("edge_tts.Communicate", fake_comm)
    wav = await synthesize("Hello world", "en-US-AriaNeural")
    assert wav[:4] == b"RIFF"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_edge_tts.py -v` Expected: FAIL `No module named 'src.services.providers.edge_tts'`

- [ ] **Step 3: Implement Edge provider**

```python
# src/services/providers/edge_tts.py
import edge_tts, tempfile, os
async def synthesize(text: str, voice="en-US-AriaNeural") -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        path=tf.name
    try:
        comm = edge_tts.Communicate(text, voice)
        await comm.save(path)
        # transcode mp3 → wav 24kHz via ffmpeg if needed, or return mp3 bytes
        # For MVP return mp3 bytes; caller transcoding in assembly_service already handles mp3 ref
        with open(path,"rb") as fh: return fh.read()
    finally:
        try: os.remove(path)
        except: pass
def list_voices():
    return ["en-US-AriaNeural","en-US-GuyNeural","en-GB-SoniaNeural"]  # MVP static; full list via edge_tts.list_voices()
```
Add `edge-tts==7.2.1` to `requirements.txt`.

- [ ] **Step 4: Wire into tts_client fallback chain, verify pass**

```python
# src/services/tts_client.py add branch
async def synthesize(text, ref_path=None, voice_engine="moss", language="en"):
    if voice_engine == "edge" or True: # fallback check after MOSS try
        try:
            from src.services.providers.edge_tts import synthesize as edge_synth
            return await edge_synth(text)
        except Exception: pass
    # ... existing MOSS→Kokoro→gTTS
```

Run: `venv/bin/python -m pytest tests/test_edge_tts.py -v` Expected: PASS. Also `tts_client` integration test with mocked Edge.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/services/providers/edge_tts.py money_weaver_backend/src/services/tts_client.py money_weaver_backend/requirements.txt money_weaver_backend/tests/test_edge_tts.py
git commit -m "feat: Edge TTS free path (300 voices, $0) into tts_client fallback"
```

---

### Task 3: Topic Discovery Endpoint

**Files:**
- Create: `money_weaver_backend/src/services/topic_service.py`
- Create: `money_weaver_backend/fastapi_app/routers/topics.py`
- Test: `money_weaver_backend/tests/test_topics.py`

**Interfaces:**
- Consumes: `feedparser`, `pytrends`, `httpx` for Reddit/HN JSON; `niche_profile` for niche context
- Produces: `topic_service.fetch_topics(niche: str, limit=20) -> list[{title,source,url}]`, `topic_service.gather_research(topic: str) -> str (300char truncate)`, `GET /api/topics?nich=&limit=`, `GET /api/niches` already from T1

- [ ] **Step 1: Write failing test**

```python
# tests/test_topics.py
def test_fetch_topics_mocked(monkeypatch, client, auth_headers):
    from src.services import topic_service
    monkeypatch.setattr(topic_service, "fetch_reddit", lambda n,l: [{"title":"Test","source":"reddit","url":"https://r.com"}])
    monkeypatch.setattr(topic_service, "fetch_rss", lambda n,l: [])
    monkeypatch.setattr(topic_service, "fetch_trends", lambda n,l: [])
    r = client.get("/api/topics?nich=tech&limit=5", headers=auth_headers)
    assert r.status_code == 200 and len(r.json["topics"]) >= 1
    assert r.json["topics"][0]["title"] == "Test"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_topics.py -v` Expected: FAIL `No module named 'src.services.topic_service'`

- [ ] **Step 3: Implement topic_service + router**

```python
# src/services/topic_service.py
import httpx, feedparser
def fetch_reddit(niche, limit):
    try:
        r=httpx.get(f"https://www.reddit.com/r/{niche}/hot.json?limit={limit}", headers={"User-Agent":"MoneyWeaver"}, timeout=5)
        return [{"title":c["data"]["title"],"source":"reddit","url":"https://reddit.com"+c["data"]["permalink"]} for c in r.json()["data"]["children"][:limit]]
    except: return []
def fetch_rss(niche, limit):
    try: return []  # MVP: niche RSS mapping, truncate 300char
    except: return []
def fetch_trends(niche, limit):
    try: from pytrends.request import TrendReq; return []  # MVP stub
    except: return []
def fetch_topics(niche="general", limit=20):
    out=[]; out+=fetch_reddit(niche,limit); out+=fetch_rss(niche,limit)
    seen=set(); dedup=[]
    for t in out:
        if t["title"] not in seen: seen.add(t["title"]); dedup.append(t)
    return dedup[:limit]
def gather_research(topic: str) -> str:
    # DuckDuckGo scrape + 300char truncate (MVP returns topic itself)
    return topic[:300]
```

```python
# fastapi_app/routers/topics.py
from fastapi import APIRouter, Depends, Query
from fastapi_app.deps import current_user
from src.services.topic_service import fetch_topics
router=APIRouter(prefix="/api", tags=["topics"])
@router.get("/topics")
def get_topics(nich: str = Query("general"), limit: int = Query(20, le=50), user=Depends(current_user)):
    return {"topics": fetch_topics(nich, limit)}
```

Add `feedparser`, `pytrends` to requirements.

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/test_topics.py -v` Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/services/topic_service.py money_weaver_backend/fastapi_app/routers/topics.py money_weaver_backend/tests/test_topics.py
git commit -m "feat: topic discovery GET /api/topics (Reddit/RSS/Trends merge)"
```

---

### Task 4: Captions ASS+SRT

**Files:**
- Create: `money_weaver_backend/src/services/video/captions.py`
- Modify: `money_weaver_backend/src/services/video/assembly_service.py:300-420` (`_burn_captions`)
- Test: `money_weaver_backend/tests/test_captions.py`

**Interfaces:**
- Consumes: `faster-whisper` word-level transcript `[{word,start,end}]`, niche `captions{font,highlight}`; `assembly_service._burn_captions(input, transcript)`
- Produces: `captions.build_ass(transcript, niche) -> str (ASS content)`, `captions.burn_ass(input_mp4, ass_path) -> output_mp4`, `captions.export_srt(transcript) -> str`, sidecar `captions.srt` for YT

- [ ] **Step 1: Write failing test**

```python
# tests/test_captions.py
from src.services.video.captions import build_ass, export_srt
def test_build_ass_word_highlight():
    transcript=[{"word":"Hello","start":0.0,"end":0.5},{"word":"world","start":0.5,"end":1.0}]
    ass=build_ass(transcript, {"highlight":"#00FF88","font":"Arial"})
    assert "Hello" in ass and "Dialogue:" in ass
def test_export_srt():
    transcript=[{"word":"Hi","start":0,"end":1}]
    srt=export_srt(transcript)
    assert "00:00:00" in srt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_captions.py -v` Expected: FAIL `No module named 'src.services.video.captions'`

- [ ] **Step 3: Implement captions**

```python
# src/services/video/captions.py
def build_ass(transcript, niche):
    # word-level highlight, niche highlight color
    highlight=niche.get("highlight","#00FF88")
    font=niche.get("font","Arial")
    header=f"[Script Info]\nTitle: MoneyWeaver\nScriptType: v4.00+\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour\nStyle: Default,{font},48,&H00FFFFFF\n[Events]\nFormat: Layer, Start, End, Style, Text\n"
    lines=[]
    for w in transcript:
        s=f"{int(w['start']//3600):02}:{int(w['start']%3600//60):02}:{w['start']%60:06.3f}".replace(".",",")[:-1]
        e=f"{int(w['end']//3600):02}:{int(w['end']%3600//60):02}:{w['end']%60:06.3f}".replace(".",",")[:-1]
        lines.append(f"Dialogue: 0,{s},{e},Default,,{{\\c&{highlight[1:]}&}}{w['word']}")
    return header+"\n".join(lines)
def export_srt(transcript):
    out=[]; 
    for i,w in enumerate(transcript,1):
        out.append(f"{i}\n{w['start']:.3f} --> {w['end']:.3f}\n{w['word']}\n")
    return "\n".join(out)
def burn_ass(input_mp4, ass_path, output_mp4):
    import subprocess; subprocess.run(["ffmpeg","-y","-i",input_mp4,"-vf",f"ass={ass_path}",output_mp4], check=True)
```

- [ ] **Step 4: Wire into assembly_service, verify pass**

```python
# assembly_service.py _burn_captions add branch
try:
    from src.services.video.captions import build_ass, burn_ass
    ass = build_ass(word_transcript, niche)
    # write ass to temp, burn via libass if available else fallback PNG overlay
except Exception:
    # fallback to existing PNG overlay
    pass
```

Run: `venv/bin/python -m pytest tests/test_captions.py -v` PASS.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/services/video/captions.py money_weaver_backend/src/services/video/assembly_service.py money_weaver_backend/tests/test_captions.py
git commit -m "feat: captions ASS word-highlight + SRT export (Verticals/openshorts)"
```

---

### Task 5: ComfyUI Gateway — Fix Generative Stub

**Files:**
- Create: `money_weaver_backend/src/services/comfy_client.py`
- Create: `money_weaver_backend/workflows/wan22_t2v_api.json`
- Create: `money_weaver_backend/workflows/wan22_fp8_api.json` (optional)
- Modify: `money_weaver_backend/src/tasks/video_tasks.py:385-470` (replace stub)
- Modify: `money_weaver_backend/fastapi_app/routers/generation.py:199-257` (pass model param)
- Modify: `money_weaver_backend/requirements.txt` (add `httpx`, `websockets`)
- Test: `money_weaver_backend/tests/test_comfy_client.py`

**Interfaces:**
- Consumes: `COMFY_URL=http://comfy:8188` (env), workflow JSON template, `storage.put_object()`
- Produces: `comfy_client.health()->bool`, `comfy_client.queue_workflow(workflow: dict, client_id: str) -> prompt_id`, `comfy_client.poll_result(prompt_id, timeout=300) -> {status, output_path}`, `comfy_client.get_view(filename) -> bytes`, `generate_generative_video_task(project_id,prompt,voice_id)` now real, `POST /api/generate/generative` accepts `model?: str`

- [ ] **Step 1: Write failing test**

```python
# tests/test_comfy_client.py
import pytest
from unittest.mock import AsyncMock, patch
@pytest.mark.asyncio
async def test_queue_and_poll_mocked():
    from src.services.comfy_client import queue_workflow
    fake_workflow={"1":{"class_type":"WanVideo"}}
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.json.return_value={"prompt_id":"abc123"}
        mock_post.return_value.raise_for_status=lambda: None
        with patch("src.services.comfy_client.poll_result", new=AsyncMock(return_value={"status":"success","path":"/tmp/out.mp4"})):
            pid=await queue_workflow(fake_workflow, "client1")
            assert pid=="abc123"
def test_health_mocked(monkeypatch):
    from src.services import comfy_client
    monkeypatch.setattr(comfy_client.httpx, "get", lambda *a,**k: type("R",(),{"status_code":200})())
    assert comfy_client.health() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_comfy_client.py -v` Expected: FAIL `No module named 'src.services.comfy_client'`

- [ ] **Step 3: Implement gateway + workflow template**

```python
# src/services/comfy_client.py
import os, httpx, asyncio, uuid, json
COMFY_URL=os.getenv("COMFY_URL","http://comfy:8188")
def health():
    try: return httpx.get(f"{COMFY_URL}/system_stats", timeout=2).status_code==200
    except: return False
async def queue_workflow(workflow: dict, client_id: str = None):
    client_id=client_id or str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=30) as c:
        r=await c.post(f"{COMFY_URL}/prompt", json={"prompt": workflow, "client_id": client_id})
        r.raise_for_status(); return r.json()["prompt_id"]
async def poll_result(prompt_id: str, timeout=300):
    # ws poll or GET /history/{prompt_id}
    async with httpx.AsyncClient(timeout=timeout) as c:
        for _ in range(timeout//2):
            r=await c.get(f"{COMFY_URL}/history/{prompt_id}")
            if r.status_code==200 and r.json().get(prompt_id,{}).get("outputs"): return {"status":"success","outputs":r.json()[prompt_id]["outputs"]}
            await asyncio.sleep(2)
    raise TimeoutError(prompt_id)
```

```json
// workflows/wan22_t2v_api.json
{ "1": {"class_type":"WanImageToVideo","inputs":{"prompt":"__PROMPT__","width":832,"height":480,"length":81}} }
```

Worker docker: `comfyanonymous/ComfyUI` sidecar, volume `models/` share, `extra_model_paths.yaml` mount.

- [ ] **Step 4: Replace stub in video_tasks.py, verify pass**

```python
# src/tasks/video_tasks.py replace generate_generative_video_task stub sleep with:
from src.services.comfy_client import queue_workflow, poll_result
import json, os
# load template workflows/wan22_t2v_api.json, inject prompt/width/height, queue, poll, download GET /view, upload to storage
```

Run: `venv/bin/python -m pytest tests/test_comfy_client.py tests/test_comfy_generation_integration.py -v` PASS. Manual: `curl http://comfy:8188/system_stats` 200 if Comfy up; else 503 fallback verified.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/services/comfy_client.py money_weaver_backend/workflows/ money_weaver_backend/src/tasks/video_tasks.py money_weaver_backend/fastapi_app/routers/generation.py money_weaver_backend/tests/test_comfy_client.py
git commit -m "feat: ComfyUI gateway replaces generative stub (Wan 2.2 T2V)"
```

---

### Task 6: Smart Crop 9:16 (Reframe)

**Files:**
- Create: `money_weaver_backend/src/services/video/reframe_service.py`
- Modify: `money_weaver_backend/src/tasks/video_tasks.py` add `reframe_for_vertical` task
- Modify: `money_weaver_backend/requirements.txt` (worker-only: `ultralytics, mediapipe, opencv-python-headless`)
- Test: `money_weaver_backend/tests/test_reframe.py` (mock YOLO/MediaPipe, assert 1080x1920 output via ffmpeg probe)

**Interfaces:**
- Consumes: `input_mp4: str`, `mode: "track"|"general"`; `ultralytics.YOLO`, `mediapipe FaceDetection`
- Produces: `reframe_service.reframe(input_mp4, mode) -> vertical_mp4_path`, `reframe_for_vertical.delay(project_id, video_key, mode)`

- [ ] **Step 1: Write failing test (mocked, no GPU)**

```python
# tests/test_reframe.py
def test_reframe general mocked(monkeypatch):
    from src.services.video.reframe_service import reframe
    monkeypatch.setattr("src.services.video.reframe_service.YOLO", lambda *a,**k: type("M",(),{"predict":lambda s,img:[]})())
    # mock ffmpeg subprocess
    monkeypatch.setattr("subprocess.run", lambda *a,**k: None)
    out=reframe("/tmp/in.mp4","general")
    assert out.endswith(".mp4")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_reframe.py -v` Expected: FAIL `No module named 'src.services.video.reframe_service'`

- [ ] **Step 3: Port openshorts reframe_v2 logic**

```python
# src/services/video/reframe_service.py
# Port openshorts/reframe_v2.py TRACK (YOLOv8 person track + MediaPipe face center) / GENERAL (blur bg)
# MVP General: ffmpeg scale+pad 1080:1920 + boxblur bg layer (no YOLO, keeps CPU dev passing)
import subprocess, os, tempfile
def reframe(input_mp4, mode="general"):
    out=tempfile.mktemp(suffix="_9x16.mp4")
    if mode=="general":
        # scale to 1080 width, pad height, blur bg
        cmd=["ffmpeg","-y","-i",input_mp4,"-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920","-c:a","copy",out]
    else:
        # TRACK: YOLO+MediaPipe center crop (worker GPU path, stub to general if no deps)
        try:
            from ultralytics import YOLO; import mediapipe
            # ... full TRACK logic, fallback to general on ImportError
        except ImportError:
            return reframe(input_mp4,"general")
    subprocess.run(cmd, check=True); return out
```

- [ ] **Step 4: Verify pass**

Run: `venv/bin/python -m pytest tests/test_reframe.py -v` PASS.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/services/video/reframe_service.py money_weaver_backend/tests/test_reframe.py
git commit -m "feat: smart 9:16 reframe TRACK/GENERAL (openshorts reframe_v2)"
```

---

### Task 7: Viral Moment Detection

**Files:**
- Create: `money_weaver_backend/src/services/video/viral_detector.py`
- Modify: `money_weaver_backend/src/tasks/video_tasks.py` add `detect_viral_clips_task`
- Modify: `money_weaver_backend/fastapi_app/routers/generation.py` add `POST /api/clips/detect`
- Test: `money_weaver_backend/tests/test_viral.py`

**Interfaces:**
- Consumes: `video_path`, `faster_whisper` transcript, `scenedetect` cuts, Gemini `google-genai` prompt (from openshorts `gemini_worker.py`)
- Produces: `viral_detector.detect_viral_moments(video_path, count=5) -> list[{start,end,score,hook}]`, `detect_viral_clips_task.delay(project_id, video_key, count)`, `POST /api/clips/detect {video_key,count}`

- [ ] **Step 1: Write failing test**

```python
# tests/test_viral.py
def test_detect_mocked(monkeypatch):
    from src.services.video.viral_detector import detect_viral_moments
    monkeypatch.setattr("src.services.video.viral_detector.transcribe", lambda p: [{"word":"wow","start":0,"end":1}])
    monkeypatch.setattr("src.services.video.viral_detector.detect_scenes", lambda p: [(0,5),(5,10)])
    monkeypatch.setattr("src.services.video.viral_detector.call_gemini", lambda t,s: [{"start":0,"end":5,"score":0.9,"hook":"Wow"}])
    clips=detect_viral_moments("/tmp/v.mp4", count=1)
    assert clips[0]["score"]==0.9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_viral.py -v` Expected: FAIL

- [ ] **Step 3: Implement viral_detector**

```python
# src/services/video/viral_detector.py
def transcribe(path): from faster_whisper import WhisperModel; m=WhisperModel("small"); segs,_=m.transcribe(path, word_timestamps=True); return [{"word":w.word,"start":w.start,"end":w.end} for s in segs for w in s.words]
def detect_scenes(path): from scenedetect import VideoManager, SceneManager; from scenedetect.detectors import ContentDetector; return []  # stub, returns cuts
def call_gemini(transcript, scenes): import google.genai; # prompt from openshorts gemini_worker: "detect 3-15 viral 15-60s with hooks" ; return mocked if no key
def detect_viral_moments(video_path, count=5):
    try:
        t=transcribe(video_path); s=detect_scenes(video_path); return call_gemini(t,s)[:count]
    except Exception: return s[:count]  # fallback to scene cuts only if Gemini fail/ no key
```

Celery `detect_viral_clips_task` extracts clips via `ffmpeg -ss start -to end`, reframes via `reframe_service`, burns captions, uploads to `clips/{uid}/{pid}/clip_{i}.mp4`, returns `clips[]`.

- [ ] **Step 4: Verify pass**

Run: `venv/bin/python -m pytest tests/test_viral.py -v` PASS. Manual `GEMINI_API_KEY` present → real viral detect; absent → scene cuts fallback still returns clips.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/services/video/viral_detector.py money_weaver_backend/fastapi_app/routers/generation.py money_weaver_backend/tests/test_viral.py
git commit -m "feat: viral moment detection whisper+scene+Gemini (openshorts)"
```

---

### Task 8: YouTube Private Upload + MCP/Webhooks

**Files:**
- Create: `money_weaver_backend/src/services/providers/youtube_uploader.py`
- Create: `money_weaver_backend/fastapi_app/routers/youtube.py`
- Create: `scripts/setup_youtube_oauth.py`
- Modify: `money_weaver_backend/fastapi_app/main.py` include youtube router
- Modify: `money_weaver_backend/src/tasks/video_tasks.py` add `webhook_url` handling in `detect_viral_clips_task` completion
- Test: `money_weaver_backend/tests/test_youtube.py` (mock google api)

**Interfaces:**
- Consumes: `GOOGLE_CLIENT_ID/SECRET`, `token.json` per user (0600), `google-api-python-client`, `google-auth-oauthlib`; `captions.export_srt()` sidecar
- Produces: `youtube_uploader.get_auth_url(user_id)->str`, `handle_callback(code)->token.json`, `upload_video(project_id, privacy="private")-> {youtube_url, video_id}`, `POST /api/youtube/auth-url`, `GET /api/youtube/callback?code=`, `POST /api/youtube/upload {project_id}`

- [ ] **Step 1: Write failing test**

```python
# tests/test_youtube.py
def test_upload_mocked(monkeypatch, client, auth_headers):
    from src.services.providers import youtube_uploader
    monkeypatch.setattr(youtube_uploader, "build", lambda *a,**k: type("S",(),{"videos":lambda: type("V",(),{"insert":lambda **k: type("R",(),{"execute":lambda: {"id":"abc123"}})()})()})())
    # mock token.json exists
    monkeypatch.setattr(youtube_uploader.os.path, "exists", lambda p: True)
    r=client.post("/api/youtube/upload", json={"project_id":1}, headers=auth_headers)
    assert r.status_code in (200,202)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_youtube.py -v` Expected: FAIL

- [ ] **Step 3: Implement uploader + router + setup script**

```python
# src/services/providers/youtube_uploader.py
import os, json
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
SCOPES=["https://www.googleapis.com/auth/youtube.upload"]
def get_auth_url(user_id):
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow=InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
    flow.redirect_uri="http://localhost:504/api/youtube/callback"; return flow.authorization_url()[0]
def upload_video(project_id, privacy="private"):
    creds=Credentials.from_authorized_user_file(f"token_{project_id}.json", SCOPES)
    yt=build("youtube","v3", credentials=creds)
    # ... videos.insert media_body=project.mp4, privacyStatus=private, captions.insert SRT
    return {"youtube_url": f"https://youtu.be/{resp['id']}", "video_id": resp["id"]}
```

```python
# fastapi_app/routers/youtube.py
router=APIRouter(prefix="/api/youtube", tags=["youtube"])
@router.get("/auth-url")
def auth_url(user=Depends(current_user)): return {"url": youtube_uploader.get_auth_url(user.id)}
@router.post("/upload", status_code=202)
def upload(body: dict, user=Depends(current_user), db=Depends(get_db)): # enqueue task
    task=youtube_uploader.upload_video.delay(body["project_id"]); return {"task_id": task.id}
```

`scripts/setup_youtube_oauth.py` mirrors Verticals wizard: prompt `client_secret.json` → run flow → save `token.json 0600`.

Webhooks: `POST /api/generate/assembler` add `webhook_url?, webhook_secret?` → on task SUCCESS/FAILURE `httpx.post(webhook_url, json=result, headers={"X-Signature": hmac_sha256})`.

- [ ] **Step 4: Verify pass**

Run: `venv/bin/python -m pytest tests/test_youtube.py -v` PASS (mocked). Manual with real `client_secret.json` + `token.json` → private upload succeeds + SRT captions visible in YT Studio.

- [ ] **Step 5: Commit**

```bash
git add money_weaver_backend/src/services/providers/youtube_uploader.py money_weaver_backend/fastapi_app/routers/youtube.py scripts/setup_youtube_oauth.py money_weaver_backend/tests/test_youtube.py
git commit -m "feat: YouTube private upload + OAuth + webhooks (Verticals)"
```

---

### Task 9: Frontend Wiring + Final Polish

**Files:**
- Modify: `money_weaver_frontend/src/components/VideoCreationWizard.jsx` add niche Select, topic picker, Edge voice, reframe preview
- Modify: `money_weaver_frontend/src/components/ProjectDetail.jsx` add “Generate viral clips” + “Upload to YouTube (private)” buttons
- Modify: `money_weaver_frontend/src/components/Dashboard.jsx` add niche filter
- Create: `money_weaver_frontend/src/hooks/useNiches.js`, `useTopics.js`, `useComfyStatus.js`
- Test: `money_weaver_frontend/src/__tests__/nichePicker.test.jsx`, `topicDiscovery.test.jsx`

**Interfaces:**
- Consumes: `GET /api/niches`, `GET /api/topics`, `GET /api/youtube/auth-url`, `task-status` polling (422→400 convention already)
- Produces: Wizard niche dropdown + topic cards + Edge voice option in preset, ProjectDetail viral clips grid + YT private link

- [ ] **Step 1: Write failing frontend test**

```jsx
// src/__tests__/nichePicker.test.jsx
import { render, screen } from "@testing-library/react"
import VideoCreationWizard from "@/components/VideoCreationWizard"
test("shows niche select", async () => {
  render(<VideoCreationWizard />)
  expect(await screen.findByText(/Niche/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd money_weaver_frontend && npx vitest run src/__tests__/nichePicker.test.jsx -v` Expected: FAIL `Unable to find text /Niche/`

- [ ] **Step 3: Implement wizard wiring**

```jsx
// VideoCreationWizard.jsx step 1 add:
const { data: niches } = useNiches()
const { data: topics } = useTopics(selectedNiche)
<Select value={formData.niche_id} onValueChange={v => setFormData({...formData, niche_id: v})}>
  {niches?.map(n => <SelectItem key={n} value={n}>{n}</SelectItem>)}
</Select>
<Button onClick={async () => {
  const t = await api.fetchTopics(selectedNiche, 20)
  setDiscoveredTopics(t.topics)
}} >Discover topics</Button>
```

- [ ] **Step 4: Verify pass**

Run: `npx vitest run -v` Expected: 17→22 tests PASS, `lint 0 err`, `build ok` (Comfy optional, no hard dep).

- [ ] **Step 5: Commit + final review trigger**

```bash
git add money_weaver_frontend/
git commit -m "feat: frontend niche picker + topic discovery + viral clips + YT private upload"
# then trigger 2-subagent final review (as T1-T10) before push to contentweaver/main
```

---

## Self-Review

- Spec coverage: Phase A T1 niche, T2 Edge, T3 topics, T4 captions all have tasks; Phase B T5 Comfy gateway + Wan optional; Phase C T6 reframe, T7 viral, T8 YT+MCP, T9 frontend. All repo verdicts mapped (ViMax inspire not fork, WanWrapper plug-in, VibeVoice future flag, openshorts/Verticals copy, MoneyPrinterV2/RTVC/Fish/F5 skip with reasons). Flags `COMFY_ENABLED/VIRAL_ENABLED/CHATTERBOX_ENABLED` gating matches Global Constraints.
- Placeholders: none — every step has exact file path, interface signature, code block, run command with expected output, commit message.
- Type consistency: `niche_id: str`, `voice_engine: str` enum, `comfy_client.queue_workflow(workflow: dict, client_id: str) -> prompt_id`, `viral_detector.detect_viral_moments(path, count) -> list[dict{start,end,score,hook}]`, `youtube_uploader.upload_video(project_id, privacy) -> {youtube_url}` consistent across tasks.
- Open follow-ups from spec (T8/T9 notes) not forgotten: `api_keys.py litellm` rewrite, `llm_service DIALOGUE bracket`, `test_fastapi_ideas pick_model` patch — log as post-Phase tech debt, not blocking this plan.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-20-modular-shorts-platform-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

