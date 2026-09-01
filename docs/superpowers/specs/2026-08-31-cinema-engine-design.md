# Cinema Engine — Overview and Plan Decomposition

Date: 2026-08-31
Status: Design (pre-implementation)
Scope: Assembler workflow (`Topic→Script→Stock→Assembly`); the same IR later
drives the generative (ComfyUI/Wan) path.

## Problem

Three mechanistic failures:
1. **Lexical retrieval bias** — keyword search against tag clouds; abstract
   nouns collapse to popularity-sorted repeats.
2. **No shot semantics** — `parse_screenplay` emits typed `action`/`camera`
   blocks but they are flattened to text and never typed.
3. **No montage** — per-shot independent selection, 3–7s duration heuristic,
   no neighbor term (Kuleshov), no pacing curve.

## Core decision

Introduce a **cinema intermediate representation (IR)** between script and
footage: `ShotSpec` (what the director wants) and `ClipRecord` (what we have),
typed with scale/angle/movement/subject/mood/duration/function. Montage =
sequence-level constrained optimization over `ClipRecord`s against ordered
`ShotSpec[]` under a montage mode + pacing curve.

## Environmental reality (verified 2026-08-31)

- PyTorch, CLIP, sentence-transformers, librosa, easyocr, imagehash,
  scenedetect: **NOT installed**.
- DB is **SQLite** (`src/database/app.db`); no Supabase/pgvector.
- Present: numpy, Pillow, cv2, av, requests, pydantic 2.13.5.

## Decisions

- **Full build, decomposed into 5 sequentially-ordered plans** (A→E), each its
  own spec → plan → build cycle.
- **Environment rule (all plans):** every heavy dependency imported behind a
  feature flag (`ENABLE_*`/`USE_*`) in `.env.example`, default-off; test suite
  passes with all absent. Install what the box can take; degrade gracefully
  where it can't.
- Existing FOOTAGE_INGEST_SERVICE.md is adopted and amended: `pgvector` →
  `sqlite-vec` behind a `VectorStore` interface; `Embedder` interface
  (torch CPU / onnxruntime / hosted Gemini); keyless sources first, free-key
  second, YouTube CC + Pond5 deferred.

## The five plans

| Plan | Deliverable | Deps | Refs |
|---|---|---|---|
| **A** | Director + ShotSpec + deterministic scorer v1 (typed, dedup) | none | `2026-08-31-cinema-plan-a-director-shot.md` |
| **B** | Footage ingest (@sqlite-vec) + ClipRecord index + retrieval | torch/onnx/Gemini embedder, sqlite-vec | amended FOOTAGE_INGEST_SERVICE.md |
| **C** | Montage planner + idiom library (pure logic) | none | `2026-08-31-cinema-plan-c-montage.md` |
| **D** | Edit timing: beat grid, phrase alignment, cut-on-action | librosa (flagged) | `2026-08-31-cinema-plan-d-timing.md` |
| **E** | Critic loop via hosted VLM | hosted VLM only | `2026-08-31-cinema-plan-e-critic.md` |

## Sequence rationale

A is zero-dependency and kills the abstract-query + dedup problems immediately;
its ClipRecord shape is a superset so B backfills embeddings without a
migration. C is pure logic on the IR from A+B. D refines timing on top of C's
plan. E adds pre-render verification hosted (no local VLM on Intel).

## Non-goals

- No new stock providers in Plan A (C/B only via ingestor interface).
- No TTS/captions/uploader changes; no ComfyUI/Wan changes in A-E (the IR is
  designed to carry over, but the generative renderer is out of scope).
- Critic loop does not re-render assembled video; it gates the plan only.
