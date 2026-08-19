# MoneyWeaver AI Engine v2 — Design Spec

Date: 2026-08-18
Status: Approved (design reviewed by user)
Scope: Text-only pass. AI-video (MiniMax generative, ComfyUI) deferred to a later pass.

## Objective

Upgrade MoneyWeaver's AI text generation layer and make video generation feel
automatic and modern: dynamic per-provider model loading (OpenRouter + NVIDIA),
per-user BYOK keys with configurable defaults + fallbacks, a one-click "random
video generator" fully written and assembled by AI, and a full screenplay-format
script pipeline. Keep assembler and generative workflows distinct, and lay
groundwork for future AI-video tagging that survives platforms devaluing AI-video.

## Non-goals (this pass)

- No real text-to-video generation (MiniMax, ComfyUI, Veo/Kling/Runway/Seedance).
- No image generation or music generation (Lyria) integration yet.
- No changes to voice cloning / TTS pipeline (MOSS-TTS + Kokoro + gTTS stay).
- No stock-footage provider changes (Pexels/Pixabay stay).

## Decisions (from brainstorming)

1. **Text-only** focus on script + assembly + everything not AI-video.
2. **Model layer**: direct provider calls, drop the Groq-only LiteLLM proxy.
3. **Keys**: per-user BYOK in Settings (encrypted), env vars as dev fallback.
4. **Script format**: full screenplay (SCENE HEADING / ACTION / CHARACTER /
   DIALOGUE / TRANSITION / CAMERA), auto-detect + manual switch, rich storyboard.
5. **Random generator**: both a standalone "Surprise Me" (one-word input) and
   per-step randomize helpers in the wizard. Distinct from manual wizard flow.
6. **Assembler vs generative**: distinct `generation_type`; assembler is real and
   default, generative remains a clearly-marked stub until a later pass.

## Current state (verified)

- `src/tasks/video_tasks.py`:
  - `generate_assembler_video_task` (:125) — REAL: LLM script → parse → TTS →
    Pexels/Pixabay stock → ffmpeg assembly → thumbnail → storage upload.
  - `generate_generative_video_task` (:380) — STUB (`time.sleep`, hardcoded
    `Wan2.2`, returns only pre-existing files).
  - `batch_mix_videos_task` (:511) — STUB (`time.sleep`, pre-existing files only).
  - `clone_voice_task` (:598) — real MOSS-TTS cloning path.
- `src/services/llm_service.py` — `litellm` SDK against LiteLLM proxy; default
  model hardcoded `groq/llama-3.3-70b-versatile` (video_tasks.py:123), mismatched
  with `/models/default` = `groq/llama-3.1-70b-versatile` (api_keys.py:215).
- `litellm_config.yaml` — Groq only.
- Frontend: 4-step wizard (`VideoCreationWizard.jsx`), model picker in Settings
  (`SettingsPage.jsx` :381-427) not persisted/wired; `language` never sent to
  backend; Dashboard "Batch Mix" button inert; no random generator.
- Infra: Redis :6379 (queue `video_generation`), LiteLLM :8000, TTS :8001,
  backend :5004 (FastAPI), frontend :5173, MinIO :9000, Postgres :5432.

## 2026 landscape (research)

- Video gen: Veo 3.1 (native audio), Kling 3.0, Runway Gen-4.5, Seedance 2.0,
  Luma Ray3, Pika, MiniMax Hailuo, Wan 2.x. Sora discontinued. APIs: Vertex,
  Replicate, fal.ai, ModelsLab, Runway. (Deferred this pass.)
- OpenRouter: 414 models, single OpenAI-compatible key, `GET /api/v1/models`
  dynamic listing, `:free` suffix = free tier (19 free: NVIDIA Nemotron, Gemma,
  GLM, `openrouter/free` router). Image-gen (GPT-5-image, Gemini-3 image) + free
  music (Lyria). No TTS/video output.
- NVIDIA NIM (build.nvidia.com): OpenAI-compatible `https://integrate.api.nvidia.com/v1`
  with `GET /v1/models`; LLM (Nemotron family, many free), Visual Design (image),
  Multimodal (Cosmos video), audio microservices.

## Architecture

### 1. Provider + model layer (`src/services/providers/`)

```
src/services/providers/
  base.py            # Provider ABC: list_models(), chat(model, messages, **kw)
  openrouter.py      # base https://openrouter.ai/api/v1
  nvidia_nim.py      # base https://integrate.api.nvidia.com/v1
  registry.py        # ModelRegistry: poll+merge+filter+cache, best_free()
```

- Both providers speak OpenAI-compatible REST (`/models`, `/chat/completions`).
- `ModelRegistry`:
  - `list_models()` → merges both providers; each entry
    `{provider, id, display_name, capabilities: {chat,image,audio}, free, context_window}`.
  - `free` determined by `pricing.prompt == "0"` or `:free` suffix (OpenRouter)
    and NVIDIA free-tier flags.
  - Cache with TTL (default 600s), thread-safe, refreshable.
  - `best_free(capability="chat")` → deterministic pick (prefer
    `openrouter/free` router, else first NVIDIA `:free` chat model).
  - `resolve(user_prefs, task)` → model id by
    `user default for task → user fallback chain → best_free`.
- `llm_service.py` rewrite: remove `litellm`; use `httpx` or `openai` SDK with
  per-provider `base_url` + `api_key`. Expose `generate_script()`,
  `generate_idea()` via the router.

### 2. Keys + settings (BYOK)

- Reuse existing `api_keys` table for provider keys: rows keyed by provider
  (`openrouter`, `nvidia`) holding Fernet-encrypted secret (key = SECRET_KEY).
- New `model_preferences` table (per-user): default model per task type
  (`script`, `idea`, fallback: `image`), ordered fallback model list.
- Endpoints: `GET/PUT /api/settings/models`, existing `/api/api-keys` for keys.
- Env fallback: `OPENROUTER_API_KEY`, `NVIDIA_API_KEY` (dev only).

### 3. Screenplay text processing

- `script_parsing_service.py` upgrade: parse screenplay elements —
  `SCENE HEADING` (INT./EXT. + location), `ACTION`, `CHARACTER` (name line
  preceding dialogue), `DIALOGUE`, `TRANSITION` (CUT TO:, FADE IN/OUT),
  `CAMERA` (angle/movement directives).
- Structured output: scenes of typed blocks; each block
  `{type, text, speaker?}`. Auto-detect via regex/rules + LLM-marked cues;
  manual override in storyboard.
- LLM script prompt updated to emit full screenplay format.
- TTS consumes `DIALOGUE` blocks (speaker → voice); captions consume typed
  blocks; `CAMERA` reserved for future assembly.

### 4. Random generator

- `POST /api/ideas/random` body `{seed?: string, language?}` → LLM returns a
  random topic + title + full screenplay. Model via `resolve(prefs, "idea")`.
- "Surprise Me": `POST /api/generate/surprise` body `{seed?, voice?, preset?,
  duration?, orientation?, ...}` → generate idea → generate script → enqueue
  assembler task (`.delay`), return 202 + task_id (same shape as assembler).
- Wizard randomize: per-step buttons calling `/api/ideas/random` (topic),
  regenerate script, randomize voice/preset pick (frontend-only).

### 5. Assembler vs generative distinct

- Add `task.generation_type` (`assembler` | `generative`), set by route.
- `/api/generate/assembler` unchanged shape + optional `model`, `idea`.
- `/api/generate/generative` stays a distinct, clearly-marked stub (returns 202,
  `generation_type=generative`, message "coming soon"). Do NOT remove — reserved
  for the later AI-video pass with `ai_generated` tagging.

### 6. Data model (Alembic migration)

- `model_preferences` table: `user_id`, `defaults` JSON, `fallbacks` JSON.
- `task.generation_type` VARCHAR (nullable, backfill `assembler`).
- `media_asset.ai_generated` BOOLEAN nullable (future AI-video tagging; not
  written this pass).

### 7. Endpoints summary

| Method | Path | Notes |
|---|---|---|
| GET | `/api/models` | live merged list (+free, capabilities, provider) |
| GET | `/api/models/default` | user default → best free |
| GET/PUT | `/api/settings/models` | per-task defaults + fallback chain |
| POST | `/api/ideas/random` | random topic + screenplay |
| POST | `/api/generate/surprise` | idea→script→assembler, 202 |
| POST | `/api/generate/assembler` | + optional `model`, `idea` |
| POST | `/api/generate/generative` | distinct stub (unchanged, marked) |

### 8. Frontend

- **Settings**: provider key entry (OpenRouter, NVIDIA) with test/delete; model
  defaults per task dropdown (populated from live `/api/models`); fallback chain
  editor; "best free" default shown.
- **Wizard**: randomize buttons per step; storyboard becomes typed-block editor
  (element type toggle per block, editable text).
- **Dashboard/new**: "Surprise Me" button + optional one-word input.
- **Model wiring**: generation requests send selected model id.

### 9. Error handling + testing

- Provider down / no key → fallback chain → clean `{error}` (never `{detail}`).
- Unit tests (mocked httpx): list/merge, free detection, resolve() ordering,
  chat fallback. Script parser: screenplay fixtures. `/api/ideas/random`:
  mocked LLM. Registry cache TTL.
- Integration: existing 220 pytest + new; coverage floor ≥ current (55).

### 10. Migration + rollout

- Alembic migration for `model_preferences` + `task.generation_type` +
  `media_asset.ai_generated`.
- Remove LiteLLM proxy: `start_all_services.sh` drop litellm launch, delete
  `litellm_config.yaml`; keep port :8000 free.
- Backward compat: `/api/models` returns merged list immediately (no key needed
  to list; chat requires key). No key → clear guidance in UI.

## Open questions (resolved during implementation)

- Exact Fernet storage location for keys (extend `api_keys` vs new column) —
  decided: extend `api_keys` with `provider` discriminator.
- `openrouter/free` router vs NVIDIA free as "best free" default — decided:
  prefer `openrouter/free`, fall back to NVIDIA `nemotron` `:free`.
