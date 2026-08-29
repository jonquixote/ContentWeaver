# ContentWeaver Studio — UX Rebuild Design

**Date:** 2026-08-27
**Status:** Approved (brainstormed + section-approved 2026-08-27)
**Reference:** `docs/examples/DialecticStudio0.html` (flow pattern), visual direction "technical studio, refined"

## Problem

The current creation flow (Dashboard → VideoCreationWizard) is disjointed: topic randomize / niche / discover / draft / enhance coexist without order or clear purpose, some features write to nowhere (description), niche discovery doesn't feed anything, generated scripts historically failed storyboard parsing, the wizard loses the app header, and there is no draft persistence. Result: users can't reach video output.

## Decision (brainstorm outcome)

**Option A — new unified Studio flow, keep backend.** Replace Dashboard + Wizard + Settings UX with one guided pipeline. Backend (FastAPI, pipeline, model hub) stays; 408 tests remain green throughout.

## Pipeline

5 locked-then-revisitable stages, gated per stage:

1. **Premise** — premise textarea + ✦suggest (random idea), duration select (30/60/90/120/180/240/300s), niche select + ✦discover (fixed: feeds premise), optional sequence link to previous project. Gate: premise non-empty.
2. **Script & Characters** — title + ✦generate, description + ✦generate (new endpoint; nothing generates description today), block ScriptEditor (existing palette) + ✦draft (`/api/scripts/draft`, premise+niche+duration), ✦enhance = improve existing only (confirm overwrite). Characters: auto-extracted + manual list. Gate: title + ≥1 parsed scene.
3. **Storyboard** — scene cards from fixed parsers; per-scene editable visual description + ✦suggest, optional reference image upload, editable duration; live total-duration chip. Gate: ≥1 scene, total within preset min/max.
4. **Style & Render** — workflow radio (assembler/generative), preset select, voice (built-in/cloned/fal inline), model overrides (moved from Settings). Gate: preset selected if presets exist.
5. **Review & Generate** — summary + estimated time → Create → enqueue → VideoProgressTracker (existing).

Cross-cutting: header always visible (fixes "wizard loses header"), per-input AI buttons, per-stage "generate all", **draft persistence** (localStorage instant → server sync at stage transitions), graceful LLM degradation (503 toast, text preserved).

## Architecture

Routes: `/dashboard` (thin project list + single "New project" CTA → /studio), `/studio/:projectId?` (the pipeline; draft Project created on first autosave), `/settings` (two cards: API keys, Model assignments), `/voices` + `/projects/:id` (unchanged). `VideoCreationWizard` deleted at the end; `/create` redirects to `/studio`.

Studio shell: `StageTabs`, `useStudioSync`, `AIGenButton`, `DraftIndicator`, five stage components.

## Data model

`Project` gains: `studio_state Text` (JSON, nullable) + `schema_version Integer default 1`. Alembic migration; existing rows → NULL = no draft.

`studio_state` shape:

```json
{
  "stage": 1,
  "premise": { "text", "durationSec", "nicheId", "sequenceProjectId" },
  "script": { "title", "description", "scriptHtml", "characters": [{"name", "traits": []}] },
  "storyboard": { "overrides": { "<sceneNumber>": { "visualText", "imageKey" } } },
  "render": { "presetId", "voiceType", "voiceId", "voiceModelOverride",
              "workflowType", "orientation", "width", "height", "language" },
  "updatedAt": "ISO"
}
```

## Endpoints (existing patterns: auth, ownership)

- `GET /api/projects/{id}/studio` → `{studio_state}` (404 none)
- `PUT /api/projects/{id}/studio` → `{saved_at}`
- `POST /api/projects/studio` → 201 draft project
- `POST /api/generate/description` `{premise, script}` → `{description}` (enhance-style route; 400/503 graceful)
- Reused: `/api/enhance-prompt`, `/api/scripts/draft`, `/api/uploads/image`, `/api/ideas/random`, `/api/topics`.

## Sync protocol

Field change → localStorage `studio-draft-{projectId}` instantly. Stage transition or 30s idle → `PUT`, then localStorage cleared. Reopen → server state wins; localStorage only if server empty.

## Visual system ("technical studio, refined")

Palette: bg `#070b12`, surface `#0c121c`, card `#111827`, accent cyan `#22d3ee`, text `#f1f5f9`, muted `#94a3b8`. Stage hues (cyan/violet/amber/emerald/rose) only as tab dots + focus rings. Inter (UI) + JetBrains Mono (script). Hairline `#1e293b` borders, 10px card / 6px input radius, one soft elevation, ghost ✦ AI buttons, 150ms ease transitions.

## Testing

- vitest: gates, sync hook precedence/conflicts, storyboard overrides, AIGenButton states; replaces wizardGenerative suite; ≥60 tests green.
- Playwright: extend existing smoke to full 5-stage pass.
- pytest: studio endpoints round-trip, 403/404 ownership, description 400/503, migration up/down; ≥55% coverage gate.

## Migration sequence (each step green, own commit(s))

1. Backend: model + 3 endpoints + description route + migration
2. Frontend: theme tokens + AIGenButton + StageTabs
3. Studio shell + PremiseStage + sync
4. ScriptStage (ScriptEditor reused) + description gen
5. StoryboardStage + uploads wiring
6. RenderStage + ReviewStage + tracker
7. Dashboard thin + Settings cleanup
8. Delete wizard + old tests; `/create` → `/studio`
9. E2E verification run (API 16/16-style + UI smoke) + progress.md entry

Rollback: per-step commits; old wizard removed last so Studio ships alongside before anything is deleted.

## Out of scope

Renderer/pipeline internals, Settings beyond the two cards, MCP/VibeVoice/deployment backlog, logo/branding.
