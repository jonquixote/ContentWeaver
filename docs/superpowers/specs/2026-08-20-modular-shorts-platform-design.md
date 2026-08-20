# Modular Shorts Platform — Design Spec
**Date:** 2026-08-20  
**Status:** Approved (C — Phased Modular)  
**Goal:** Keep MoneyWeaver core `FastAPI+Celery+ffmpeg+stock`, graft 3 external subsystems as isolated modules. No fork, no rewrite. 6-week balanced plan. Phased CPU-now GPU-later, commercial-safe (MIT/Apache only).

## Context

MoneyWeaver after T1–T10: FastAPI 504 + Celery+Redis, `assembly_service` (stock Pexels/Pixabay + ffmpeg), TTS `MOSS-ONNX 8001 → Kokoro 82M → gTTS`, presets, `script_parsing_service` typed blocks (heading/action/character/dialogue/transition/camera), model registry `OpenRouter/NVIDIA` with `defaults/fallbacks/best_free`, storage local/S3, 241 backend + 17 frontend tests, 60.9% cov.

Gaps: `generate_generative_video_task` is stub (sleep 5s), no viral moment detection, no smart 9:16 crop, no niche-aware generation, no $0 TTS path, no topic discovery, no YouTube private upload, single-voice only.

External repos investigated (8 + 7 discovered): ViMax 12k, ComfyUI 128k, WanWrapper 6.6k, VibeVoice 595, openshorts 3.2k, youtube-shorts-pipeline (Verticals) 2.2k, MoneyPrinterV2 31k AGPL, RTVC 60k stale, plus Coqui 46k, OpenVoice 37k, Chatterbox 26k SoTA, Fish S2 NC, CosyVoice, F5 NC, Zonos, Tortoise, Bark. Verdicts in repo tables below.

## Architecture Overview

```
[Frontend Wizard] → [FastAPI Routers] → [Services]
      │                     │                  │
   presets           generation  topics  settings  llm_service (niche-aware)
      └────────────┬────────┴────────┴────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
   Celery Tasks  ComfyUI GW  TTS Router
  assembler ✓   generative   MOSS→Edge→(GPU:Chatterbox)
  viral_detect  WanWrapper   VibeVoice (future 4-speaker)
  batch_mix     (optional)   OpenVoice (style, optional)
        │
   [Storage] → [YouTube Uploader] (private-by-default, OAuth)
```

**Isolation principle:** Each graft behind interface, one purpose, well-defined call, testable independently. Existing callers (`generation.py::_enqueue_assembler`, `video_tasks.py`) keep same signatures; only internal dispatch changes.

- `src/services/providers/niche_profile.py` loads `niches/*.yaml` → feeds `llm_service.generate_script(prompt, niche_id?)`
- `src/services/tts_client.py` router: `Voice.voice_engine` → `moss|edge|kokoro|gtts` (CPU) → later `chatterbox` (GPU)
- `src/services/comfy_client.py` httpx → `http://comfy:8188/prompt` + ws poll, replaces stub `video_tasks.py:448`
- `src/services/video/reframe_service.py` wraps `reframe_v2.TRACK/GENERAL`, `viral_detector.py` wraps `gemini_worker.detect()`
- `src/services/providers/youtube_uploader.py` wraps `google-api-python-client`

## Phase A — Quick Wins (wk1-2, CPU-only, Effort 1-2)

1. **Niche Profiles** `money_weaver_backend/niches/*.yaml` (copy 15 Verticals profiles)
   - Schema: `name,tone,hooks[],forbidden[],visuals{style,palette},captions{font,highlight},music{genre},word_count`
   - Wire into `llm_service.generate_script(prompt, niche_id?)` via `niche_profile.load(niche_id).inject(tone,hooks)` before `SCREENPLAY_PROMPT`. Fallback to defaults if no niche.
   - API: `GET /api/niches`, `POST /api/generate/assembler` add optional `niche_id` (backward compat).
   - Also steal `verticals/research.py` anti-hallucination gate: `gather_research(topic)` (DuckDuckGo scrape, 300char truncate) → pass as context to LLM.
   - Source: `verticals/niche.py`, `niches/tech.yaml`, `research.py`

2. **Edge TTS** `src/services/providers/edge_tts.py` (`edge-tts==7.x`, 300 voices, $0, MIT)
   - Add to `tts_client.py` chain: `MOSS-ONNX (8001) → Edge → Kokoro 82M → gTTS`
   - Trigger: `Voice.voice_engine=='edge'` or fallback when MOSS 503. No env, `pip install edge-tts`.

3. **Topic Discovery** `GET /api/topics?nich=tech&limit=20` → `src/services/topic_service.py`
   - Sources from `verticals/topics/`: Reddit json, RSS `feedparser`, `pytrends`, HN Algolia. Merge/dedup `{title,source,url}`.
   - Frontend: Wizard step 1 “Discover topics”.

4. **Captions ASS+SRT** `src/services/video/captions.py`
   - Port `verticals/captions.py` (Whisper small → word-level ASS yellow `#00FF88` + SRT) + `openshorts/subtitles.py` niche fonts/CJK.
   - Integrate into `assembly_service._burn_captions()` via ffmpeg `ass` filter, fallback to current PNG overlay if libass missing. Export SRT sidecar for YT.

**Acceptance Phase A:** Niche-shaped script generates; Edge TTS 5s audio $0; `GET /api/topics` 10+ topics <2s; word-level ASS + SRT produced.

## Phase B — ComfyUI Gateway (wk3-4, GPU-ready)

**Problem:** `video_tasks.generate_generative_video_task` stub sleep 5s.

- **Gateway** `src/services/comfy_client.py`: `POST http://comfy:8188/prompt {"prompt": workflow, "client_id": uuid}` + ws `ws://comfy:8188/ws?clientId=` poll `execution_success`/`progress`. Download via `GET /view` → `storage.put_object(videos/{uid}/{pid}/{task})`.
- Template `workflows/wan22_t2v_api.json` (Wan 2.2 14B / 1.3B). Params inject from `generation.py:AssemblerRequest` (preset→width/height/orientation, prompt, `model` flag).
- Celery task replaces stub: load template → inject → `comfy_client.queue()` → poll → upload → update `Task`. Fallback to `503 {error:"ComfyUI unavailable"}` or `fallback_to_assembler` flag.
- **WanWrapper** `kijai/ComfyUI-WanVideoWrapper` as `ComfyUI/custom_nodes/` plug-in (not MoneyWeaver dep). For `fp8_scaled` 14B on 16GB VRAM, `context_windows` 1025f (81 win/16 overlap <5GB), `ReCamMaster`. Expose via `model="wan22_fp8"` selects `wan22_fp8.json` vs `wan_native.json`. Default native Wan. Flag `WAN_WRAPPER_ENABLED`.
- **Comfy sidecar** docker `comfyanonymous/ComfyUI:8188` + volume `models/` shared, `extra_model_paths.yaml` to share `diffusion_models/vae/text_encoders`.
- **TTS evolution (phased):** NOW keep `MOSS+Kokoro+gTTS+Edge`. GPU prod adds `src/services/providers/chatterbox_provider.py` (Resemble `chatterbox` Turbo 350M/Nano 110M, 23 langs, MIT, RTF 0.04 GPU / Nano 3x CPU) when `torch.cuda.is_available()`. Toggle `CHATTERBOX_ENABLED`. Future `VibeVoice 1.5B 64K` via Comfy node for 4-speaker 90min podcast behind `VIBEVOICE_ENABLED` (separate multispeaker workflow, not cloning path; needs CUDA+bitsandbytes 4-bit).

**Acceptance Phase B:** `POST /api/generate/generative {prompt}` → `202` → `task-status SUCCESS` with real mp4 in storage; Comfy down → 503.

## Phase C — Shorts Automation (wk5-6)

1. **Smart 9:16 Crop** `src/services/video/reframe_service.py`
   - Port `openshorts/reframe_v2.py` + `active_speaker.py`. Modes `TRACK` (MediaPipe face + YOLOv8 person track, center speaker 1080x1920) / `GENERAL` (blur bg fallback, opencv).
   - Celery `reframe_for_vertical(input_mp4, mode)` called when `orientation=portrait` + `source_type=upload`. Deps (`mediapipe`, `ultralytics`) in worker image only (+3.5GB weights, not API image).

2. **Viral Detection** `src/services/video/viral_detector.py`
   - Port `openshorts/gemini_worker.py` + `scene_detection.py` (PySceneDetect + `faster-whisper` 1.2.1 word-ts). Flow: `long.mp4 → faster-whisper → scene cuts → Gemini 3.0 Flash "detect 3-15 viral 15-60s hooks" → [{start,end,score,hook}] → ffmpeg extract → reframe → captions`.
   - Celery `detect_viral_clips_task(project_id, video_key, count=5) → clips[]` with PROGRESS. Frontend ProjectDetail button.

3. **YouTube Auto-Upload** `src/services/providers/youtube_uploader.py`
   - Port `verticals/upload.py`: `google-api-python-client + google-auth-oauthlib`, OAuth2 `InstalledAppFlow` → `token.json 0600` per user, `videos.insert` `privacyStatus=private` + `captions.insert` SRT.
   - Setup `scripts/setup_youtube_oauth.py`; API `GET /api/youtube/auth-url`, `GET /api/youtube/callback`, `POST /api/youtube/upload {project_id}`.

4. **MCP + Webhooks** (light)
   - `POST /api/process` add `webhook_url,webhook_secret` → on `Task SUCCESS/FAILURE` → `httpx POST` with `HMAC sha256 X-OpenShorts-Signature`. MCP tools `process_video,get_job_status,list_clips,publish_clip` at `GET /mcp/tools`.

**Skip:** MoneyPrinterV2 MoviePy/Selenium AGPL (cherry-pick only cron idea → already have `apscheduler`), CorentinJ RTVC stale SV2TTS (successor Chatterbox).

## Data Flow & Error Handling

**Flows:**
- `Topic→Script`: `GET /api/topics` → `POST /generate/assembler {prompt,niche_id}` → `llm_service` niche-inject → `SCREENPLAY_PROMPT` → `parse_screenplay()` → `Task assembler`.
- `Assemble`: `gather_research?` → `shot_descriptions` (action/camera blocks) → `stock_footage_service` → `tts_client` router → `assembly_service` ffmpeg → `captions` ASS → `storage.put_object(videos/...)` → presigned.
- `Generative`: same prompt → `comfy_client.queue(Wan)` → ws poll → `GET /view` → `storage.put_object`.
- `Long→Shorts`: `detect_viral_clips` → `whisper+scene+Gemini` → `extract+reframe+captions` per clip → `youtube_uploader` private.

**Errors:** `.delay()` wrapped `try/except → 503 {error:"Task queue unavailable"}` + `db.delete(task);commit()` + file cleanup (P2/P4 pattern). Comfy down → 503, not 500. Viral/Gemini fail → fallback to scene cuts only. TTS cascade preserved MOSS→Edge→Kokoro→gTTS. Presigned URLs `?token` only for `/-paths`, never absolute S3 (Phase 4 F2 fix).

**Security/Commercial:** MIT/Apache only. Block AGPL (MoneyPrinterV2), NC weights (Fish S2, F5 CC-BY-NC, VibeVoice model CC-BY-NC). `STORAGE_*,COMFY_URL` via `${VAR:-default}`, secrets in `.env 0600`.

## Testing & Rollout

- **Backend pytest** 241 → +15 new: `test_niches, test_topics, test_edge_tts, test_comfy_client (mock httpx queue+ws), test_reframe, test_viral (mock Gemini), test_youtube_uploader (mock google api)`. Keep fail-under 55, target 60%+ (now 60.9).
- **Frontend vitest** 17 → +5: niche picker, Edge TTS select, viral clips list. GPU paths mocked.
- **Staged verify:** Phase A curl `GET /api/niches` + Edge 5s audio; Phase B `ComfyUI:8188` health + `queue→SUCCESS` redis; Phase C `faster-whisper` 8min CPU 5min vs GPU 50s bench.
- **Rollout:** Wk1-2 Phase A merge → main, no GPU. Wk3-4 Phase B behind `COMFY_ENABLED` flag (off Intel dev, on `docker-compose` GPU prod). Wk5-6 Phase C behind `VIRAL_ENABLED` (needs 3.5GB YOLO). Each PR small, lint+build green, 2-reviewer pass (T1–T10 process).

## Repo Verdicts Summary

| Repo | Stars | Verdict | Why |
|------|-------|---------|-----|
| HKUDS/ViMax | 12k MIT | INSPIRE | Steal agentic loop/prompts/pipeline, don’t fork. Heavy cloud-API bill, opposes local Comfy. |
| Comfy-Org/ComfyUI | 128k GPL-3 | USE | Real generative server, replace stub. Wire `POST /prompt` + ws. |
| kijai/WanWrapper | 6.6k Apache | USE (plug-in) | fp8 14B on 16GB, 1025f context windows, latest research wrappers. Optional. |
| wildminder/VibeVoice | 595 MIT (model CC-BY-NC) | REPLACE (future) | 4-speaker 90min podcast via Comfy node. Phase B single-voice keep MOSS; GPU future. |
| mutonby/openshorts | 3.2k MIT | COPY | Viral detect + smart crop `reframe_v2` TRACK/GENERAL + `subtitles.py` + `active_speaker`. Best short→viral. |
| Verticals pipeline | 2.2k MIT | COPY | Niche YAML + Edge TTS free + topic discovery + research gate + yt private upload. Easiest wins. |
| MoneyPrinterV2 | 31k AGPL | SKIP | Selenium brittle, MoviePy legacy, AGPL poison. Only cherry-pick cron idea. |
| CorentinJ RTVC | 60k NOASSERTION stale | SKIP | 2019 SV2TTS, MOS 3.5 vs SoTA 4.3+, author says use Chatterbox successor. Use babCoqui/Chatterbox instead. |
| coqui-ai/TTS (XTTS v2) | 46k MPL-2 | USE conditional | 16 langs, <200ms streaming. Company shut 2024 stale, needs torch 2.4+ (Intel Mac blocked). GPU prod alternative. |
| myshell OpenVoice V2 | 37k MIT | REPLACE candidate | Tone-color converter, style control, 6 langs, <4GB VRAM. MIT. Optional. |
| resemble Chatterbox | 26k MIT active | COPY/USE | 2025 SoTA Turbo 0.04 RTF / Nano 3x CPU, 23 langs, watermark toggle. Successor to RTVC, phased GPU prod. |
| fish S2 Pro | 32k Research NC | SKIP | 4B H200, NC license, not SaaS. Inspire tag design only. |
| CosyVoice 3 | 23k Apache | INSPIRE | Streaming 150ms, heavy CN-centric. Skip direct use. |
| F5-TTS | 15k MIT/NC | SKIP | NC weights due Emilia, skip commercial. Copy Sway Sampling. |

## Decisions

- Goal: Modular platform (C) — keep core, add graftable modules.
- Constraints: All above — commercial MIT/Apache, GPU prod planned, CPU dev now → phased: CPU wins first, GPU later.
- Success: Balanced 6wk: 2wk quick wins + 2wk Comfy gateway + 2wk shorts automation, all commercial-safe.

## Open Follow-ups (T8/T9 notes, logged for implementation)

- `fastapi_app/routers/api_keys.py: test_api_key` still uses `litellm.completion` against removed LiteLLM proxy → rewrite to httpx providers (openrouter/nvidia) (T5 note).
- `src/services/llm_service.py:84-85` fallback `DIALOGUE:` unbracketed → parser misclassifies as action; bracket `[DIALOGUE: ...]` (T6 minor).
- `tests/test_fastapi_ideas` must also monkeypatch `pick_model` else real network ~13s (T7 note).
- `money_weaver_frontend/src/services/api.js` already has `randomIdea/generateSurprise` for T10; verify `generate_surprise` sig uses `seed/voice_id/preset_id` plus `model` param passthrough to `llm_service.generate_idea` and `_enqueue_assembler`.

## Alternatives Considered

- A Minimal Graft (Verticals-only): 1wk fast but generative stub remains.
- B Full Fork ViMax: powerful agents but heavy, cloud-billed, loses assembler+stock edge.

Selected C for balanced risk, commercial safety, CPU-now GPU-later.

## Spec Self-Review

- Placeholders: none (all verdicts concrete, file paths with lines).
- Consistency: Phased flags `COMFY_ENABLED/VIRAL_ENABLED/CHATTERBOX_ENABLED` match architecture; no AGPL/NC in selected path.
- Scope: Single 6wk modular graft, decomposable into 3 phases, each shippable independently.
- Ambiguity: `niche_id` optional backward compat clarified; `VibeVoice` explicitly future, not Phase B default, to avoid scope creep.

