# SDD Progress Log — ContentWeaver

One line per completed plan/phase; latest phase detailed. Plans live in `docs/superpowers/plans/`.

## Phase History

- **2026-08-21 — Phase D: Pipeline Completion** — plan `2026-08-21-phase-d-pipeline-completion.md`; backend pipeline stages completed and verified.
- **2026-08-21 — Phase E: Chatterbox Voice Cloning** — plan `2026-08-21-phase-e-chatterbox-voice-cloning.md`; voice-cloning service wired end-to-end.
- **2026-08-21 — Phase F: Generative Enablement** — plan `2026-08-21-phase-f-generative-enablement.md`; generative services enablement groundwork.
- **2026-08-24 — Phase G1: Model Provider Hub** — plan `2026-08-24-g1-model-provider-hub.md`; model provider registry + assignments hub.
- **2026-08-24 — Phase G2: Generative Integration** — plan `2026-08-24-g2-generative-integration.md`; wizard generative integration, external-value sync for ScriptEditor.
- **2026-08-26 — Phase G3: Block Screenplay Editor** — plan `2026-08-24-g3-block-screenplay-editor.md`; detailed below.

## Phase G3: Block Screenplay Editor (2026-08-24 → 2026-08-26)

**Goal:** block-based screenplay editing in ScriptEditor (draggable + click-to-insert palette, prefilled dual-parser-compatible blocks, character autocomplete) serializing to the `**Scene N (Xs-Ys)**` + `Voiceover:` canon.

### Tasks

| Task | Scope | Commit |
|------|-------|--------|
| 1 | `src/lib/screenplayBlocks.js` — BLOCK_TYPES, parseScreenplay, serializeScreenplay, extractCharacters, seedBlocks, blockToInsertContent + unit tests | `9e15d66` |
| 2 | ScriptEditor palette — 5 chips, click-insert via `insertContentAt`, HTML5 drag-drop, scene-header renumbering, characters hint | `40df376` |
| 3 | Wizard round-trip — draft script output → `serializeScreenplay(parseScreenplay(...))` → storyboard compatibility | `4886fd0` |
| — | Fixes: wizard test stability (15s timeout); replace-script confirms | `91b3726`, `681eb5e` |
| — | Deps hygiene: ML extras split, Pillow/gtts; typing_extensions pin docs | `9d0f317`, `2eb88f7` |

### Task 4 Close-out Gates (2026-08-26)

- **Frontend vitest:** 57/57 passed, 21 files (gate ≥49 ✓)
- **Frontend build:** `vite build` ok, 8.4s (chunk-size warning pre-existing)
- **Backend spot check:** `pytest -k "script or wizard or api"` → 91 passed, 317 deselected (408 total, matches baseline)

### Live Smoke (2026-08-26, driven Playwright/chromium)

Environment: backend uvicorn on :5005 (repo `run.py`, venv outside repo), frontend vite on :5199 with `VITE_API_URL=/api` + proxy config (target :5005; note: `src/services/api.js` defaults to absolute `http://localhost:5004/api`, so the env var is required for the proxy path).

Backend venv is ephemeral (`/var/folders/j5/_4pw7zgd6m7f_l0dmh63gk680000gn/T/opencode/venv-t1`, Python 3.12). Recreate with: `python3.12 -m venv <path> && pip install -r money_weaver_backend/requirements.txt`.

Flow driven: UI register → dashboard → `/create` wizard → clicked all 5 palette chips (scene header, voiceover, visual, dialogue, transition) → characters hint showed `NAME` → second scene (header + voiceover per canon) → Next → storyboard step rendered **2 scene cards** from inserted blocks. 11/11 checks passed.

Evidence: `/var/folders/j5/_4pw7zgd6m7f_l0dmh63gk680000gn/T/opencode/smoke/` — `smoke.cjs`, `result.json`, `01-register-filled.png`, `02-editor-blocks-inserted.png`, `03-storyboard-scenes.png`.

### End-to-End Verification (2026-08-26)

Fresh-boot verification at HEAD: backend `run.py` on :5004 (SQLite, SECRET_KEY set), vite dev :5173.
- API E2E script (register→me→presets/niches/topics→api-keys→models catalog(490)→model-assignments→projects CRUD→ideas/draft graceful degradation): **16/16 PASS**
- UI Playwright smoke vs :5173 (register→wizard→all 5 palette chips→characters hint→storyboard scenes): **11/11 PASS**
- Gates: vitest **57/57**, pytest **408 passed** (coverage 67.84%), `vite build` ✓ 9s
- Note: without LLM provider keys `/api/ideas/random` → 503, `/api/scripts/draft`+`/api/enhance-prompt` → 400 — graceful by design.

### Findings (non-blocking, no feature code changed)

1. **Seed wipe in dev StrictMode:** ScriptEditor's empty-editor seed (sceneHeader+voiceover) is applied then wiped by React StrictMode's double-invoked effect — `seededRef` is already `true` on the second run, so the external-sync branch calls `setContent('')` (ScriptEditor.jsx:38-53). Dev-only; production build unaffected; unit tests (jsdom) don't exercise the double-invoke. Palette insertion unaffected — chips insert correctly regardless.
2. **Visual chip prefill is empty** by design (`blockToInsertContent` default → empty paragraph); invisible in the editor but structurally inserted.
3. **Scenes require `Voiceover:` line after each header** — `SCENE_PATTERN` in `scriptParser.js` only counts header+voiceover pairs; a trailing header alone yields no scene card. Canon behavior; wizard warns accordingly.

### S1 Studio backend persistence (2026-08-29)

Backend contract for Studio landed: `Project.studio_state` (TEXT, nullable) + `schema_version` (INT default 1) with lightweight `ALTER TABLE` migration in lifespan; `POST /api/projects/studio` (201 draft), `GET /api/projects/{id}/studio`, `PUT /api/projects/{id}/studio` (ownership 403/404); `POST /api/generate/description` (premise+script → description, 400/503 graceful). Commits 57a95e2, ec6318e, 34774d1. Suite 415 passed (68.11%).

### S2 Studio shell + Premise (2026-08-29)

Design tokens (`--studio-*` CSS vars in index.css), `AIGenButton` (ghost ✦, spinner, toast errors), `studioState.js` (default state, STAGES, DURATIONS, `validateStage`/`sceneCount`), `StageTabs` (locked-then-revisitable), `useStudioSync` (localStorage instant + server PUT at stage transitions, server-state-wins on load, 404→null), `api.js` studio methods, `/studio` + `/studio/:projectId` routes, `Studio.jsx` shell, `PremiseStage`. Commits e9b4bf0, 3232bc6, 5b1bbb3, d02a0d8. vitest 76/76, vite build ok.

### S3 ScriptStage (2026-08-29)

`ScriptStage` (title ✦ via enhance-prompt, description ✦ via `/generate/description`, draft ✦ canonicalized through `scriptTextToHtml` (new `lib/studioUtils.js`), enhance ✦ improve-only w/ confirm, characters auto-extract + manual add/remove). Wired stage 2 in Studio.jsx. vitest 83/83, build ok.

### S4 StoryboardStage (2026-08-29)

`StoryboardStage` (scene cards via `parseScriptText`, per-scene visual textarea + ✦suggest, editable duration + live total chip, reference image). **Deviation:** backend has no image-upload endpoint (`/uploads/presign` is audio-only), so reference image is stored as a client-side data-URL in `overrides[].imageKey` (preview only; does not feed render pipeline). vitest 90/90, build ok.

### S5 Render + Review (2026-08-29)

`RenderStage` (workflow radio, preset→orientation/dims, voice type, cloned voice, fal API voices → `voiceModelOverride`, text model override via ModelPicker, language) and `ReviewStage` (summary grid, estimated time, Create → reuses draft `projectId`, assembler/generative enqueue → `VideoProgressTracker`). Added `render.textModelOverride` (additive) to state contract. Wired stages 4-5 in Studio.jsx. vitest 97/97, build ok.
