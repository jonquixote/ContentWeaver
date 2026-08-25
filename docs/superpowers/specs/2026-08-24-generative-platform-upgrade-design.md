# Generative Platform Upgrade — Design Spec

Date: 2026-08-24
Status: Approved direction (user)
Phases: G1 (Model & Provider Hub) → G2 (Generative Integration) → G3 (Block Screenplay Editor)
Constraints: MIT/Apache/BSD freely, LGPL dep-only, AGPL/NC blocked (fal-client MIT — allowed). CPU dev machine; API/GPU generation flag-gated where costly. Repo root `/Volumes/JOHNNY DISK/MoneyWeaver`.

---

## G1: Model & Provider Hub

### Goal
One place to see every model the platform can use — searchable, filterable by provider/free/capability — plus per-task assignments (idea / script / enhance / voice_tts / video_gen) that every generative feature respects.

### Provider abstraction (backend)
- Extend existing `ModelRegistry` protocol: each provider's `list_models()` entries gain `kind` ∈ {text, voice, video} alongside id/provider/display_name/free.
- New `src/services/providers/fal_adapter.py`: fal.ai integration.
  - Auth: per-user `FAL_KEY` stored via existing ApiKey table + Fernet encryption (provider name `fal`). Same pattern as OpenRouter keys.
  - Catalog: curated static list of vetted fal endpoints (voice TTS + text-to-video), each `{id, kind, display_name, provider:'fal', free:False, inputs_schema_summary}`. Live catalog query deferred.
  - Execution: `fal_client.submit()` → poll status → result URL → download bytes. Fits Celery task bodies (mirrors comfy_client flow).
- Key-added hook: POST /api/api-keys invalidates registry cache and warms the new provider's catalog (so models appear immediately).
- `GET /api/models?kind=&q=` returns merged catalog with kind tags.

### Assignments
- New table `model_assignment(id, user_id, task, model_id, created_at, updated_at)`; unique (user_id, task). Tasks: `idea`, `script`, `enhance`, `voice_tts`, `video_gen`.
- Migration chained on current head `b7e1d2c3a4f5`.
- `resolve_model_for(user_id, task)` helper: assignment → else sensible default (idea/script/enhance: registry best_free; voice_tts: local chain 'auto'; video_gen: 'comfy_local' if COMFY_ENABLED else first fal video model).
- Routes: GET/PUT `/api/model-assignments` (auth-scoped).
- Consumption points wired: ideas router, generate_script, enhance endpoint (G2), voice selection in assembler/generative tasks (voice_tts='auto' keeps MOSS→Edge→Kokoro→gTTS chain; a fal voice id routes through fal adapter), video generation picks comfy-local vs fal by assignment.

### Frontend
- Reusable `<ModelPicker>` component: text search, provider filter chips, Free badge, capability tabs, alphabetical+free-first sort. Backed by GET /api/models.
- Settings page new "Model Assignments" card: five rows (task label + ModelPicker), PUT on change.
- Wizard inline overrides: compact ModelPicker next to each generate control, pre-seeded from assignments, override persisted per-wizard-session only.
- Voice step lists local voices AND fal voices (badge "API"); video step shows ComfyUI-local option when enabled plus fal video models.

### Testing
- Unit: catalog merge/kind filter; resolve_model_for precedence; fal adapter request/poll/download shapes (mocked fal_client); key-hook cache invalidation.
- Integration: assignments CRUD; /api/models filtering; generative task honoring voice_tts/video_gen assignments (mocked adapters).
- E2E smoke: save fal key → fal models appear in picker → assign → generate stubbed.

---

## G2: Generative End-to-End Integration

### Goal
Every generative affordance works from every surface, respects assignments, and lands results into adjacent manual inputs as editable text.

### Behaviors
- Randomize Topic (wizard + dashboard): fills title + prompt fields (works today; kept reliable via G1 assignments).
- NEW Enhance wand on prompt textareas (wizard step 1, generative panel): POST `/api/enhance-prompt {text, style_hint}` → llm rewrite using `enhance` assignment → replaces textarea content with undo toast.
- NEW Draft Script button in wizard step 2: generates screenplay from current topic/niche via `script` assignment into the editor (replaces empty or confirms overwrite).
- Voice step: shows assigned voice engine; explicit fal voice → fal TTS bytes through existing write_voice_audio path.
- Video step: assignment `video_gen=comfy_local` → existing comfy path; fal model → fal adapter path producing mp4 into same storage layout (`generative/{pid}/...`).
- All failures: typed error toasts (rate-limited/unavailable/no-key) with retry; never silent fallbacks that confuse.

### Backend
- `POST /api/enhance-prompt` (new, auth): uses `enhance` assignment; reuses _chat_free_resilient.
- video_tasks.generate_generative_video_task branches on resolved video_gen target (comfy vs fal) behind shared interface `VideoBackend.render(prompt, width, height, seed) -> bytes`.

### Testing
- Unit: enhance endpoint (mocked llm), VideoBackend branch resolution.
- Integration: wizard flows via component tests with msw: randomize→fields populated; enhance→textarea updated; draft script→editor receives screenplay.
- Task-level: fal video backend mocked submit/poll/download → put_object key parity with comfy path.

---

## G3: Block Screenplay Editor

### Goal
Replace the raw-textarea script editing experience with block-based screenplay editing that serializes to exactly what `script_parsing_service` parses.

### Blocks (TipTap custom nodes)

PLANNING DISCOVERY: two script parsers exist — frontend `src/lib/scriptParser.js` (storyboard
step) and backend `script_parsing_service.py` — and BOTH accept the same core canon:
`**Scene N: Name (Xs-Ys)**` headers + `Voiceover: "..."` lines (backend additionally accepts
`[DIALOGUE: ...]`, UPPERCASE character names, transitions). G3 serializes to this
dual-compatible canon so storyboard AND assembler keep working from one document:

| Block | Serialized form | Prefill pattern |
|---|---|---|
| sceneHeader | `**Scene 1: INT. LOCATION - DAY (0s-5s)**` | auto-numbered; durations auto-sum |
| voiceover | `Voiceover: "..."` | empty quotes to fill |
| visual | plain prose line(s) under header | shot description |
| dialogue | `CHARACTER NAME:` line + `[DIALOGUE: line]` | name autocomplete from doc |
| transition | `CUT TO:` / `FADE OUT.` | dropdown of common transitions |

- Palette above editor: one chip per block type. Each chip is HTML5-draggable (drop at caret position inserts node there) AND click-to-insert (inserts after the block containing the cursor).
- Character autocomplete: TipTap suggestion utility sourcing distinct character names already present in the document.
- Load path: parse existing scene-format text (patterns above) into block nodes. Save path: serialize nodes back to canonical plain text before persisting to Project.script.
- Empty editor defaults to one sceneHeader + one voiceover block (never a bare textarea).

### Testing
- Unit: serializer round-trip (blocks→text→blocks stable); parser compatibility fixtures for every block type; autocomplete source extraction.
- Component: palette click inserts expected node at position; drag-drop insertion; prefill contents match table.
- Integration: draft-script (G2) populates blocks; saved text passes script_parsing_service.parse_script with expected block types.

---

## Sequencing & execution
G1 → G2 → G3, each phase: spec section above → implementation plan → subagent-per-task with review gates (established SDD process). Shared files across phases noted per plan. Baseline: 381 backend tests, 25 frontend tests, all green.

## Out of scope (this upgrade)
Replicate adapter, image-model inference, streaming token UI, multi-model comparison view, collaborative editing, BYO-endpoint custom providers.
