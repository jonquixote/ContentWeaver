# Cinema Plan A — Director, ShotSpec, Deterministic Scorer

Date: 2026-08-31
Status: Design (pre-implementation)
Parent: 2026-08-31-cinema-engine-design.md (supersedes as the canonical per-plan specs)
Scope: `money_weaver_backend` — new `src/services/cinema/`. No new dependencies.
Depends on: nothing. Independently valuable and testable.

## Problem

`_generate_search_queries` reduces a shot to ≤3 keywords; `parse_screenplay`
emits `action`/`camera` blocks but `extract_shot_descriptions` flattens them
to text; `_rerank_candidates` is a per-shot text-score with no shot semantics,
no typed ClipRecord, and no dedup except keyword blocklist. Result: abstract
queries, no shot knowledge, repeated/off-theme clips surviving.

## Goal

Produce an ordered list of **typed `ShotSpec[]`** and a **deterministic scorer**
that (a) turns L1 into filmable requests, (b) scores any candidate against a
ShotSpec using typed fields + neighbor term + dedup, (c) never blocks a render
when the LLM is unavailable.

## Design

### 1. Typed enums (`cinema/types.py`)

```python
class ShotScale(str, Enum):
    ECU="ecu"; CU="cu"; MCU="mcu"; MS="ms"; MLS="mls"; LS="ls"; ELS="els"; ABSTRACT="abstract"
class CameraMove(str, Enum):
    STATIC="static"; PAN="pan"; TILT="tilt"; DOLLY_IN="dolly_in"; DOLLY_OUT="dolly_out"
    TRACK="track"; HANDHELD="handheld"; DRONE="drone"; CRANE="crane"; ZOOM="zoom"
class ShotFunction(str, Enum):
    ESTABLISH="establish"; CONTEXT="context"; DETAIL="detail"; REACTION="reaction"
    SYMBOL="symbol"; TRANSITION="transition"; PAYOFF="payoff"
class MontageMode(str, Enum):
    METRIC="metric"; RHYTHMIC="rhythmic"; TONAL="tonal"; OVERTONAL="overtonal"; INTELLECTUAL="intellectual"
```

### 2. ShotSpec (`cinema/shot.py`)

Pydantic model. **Nullable typed fields** (embedding/scale/move) are part of
the shape NOW so Plan B is a backfill, not a migration — agreed amendment.

```python
class ShotSpec(BaseModel):
    scene_number: int
    shot_index: int
    narrative_beats: str          # voiceover/dialogue span this shot covers
    subject_concrete: str         # "hands counting cash" — never "wealth"
    scale: ShotScale
    move: CameraMove
    function: ShotFunction
    mood: str                     # "cold/dim", "warm/golden" — tonal target
    screen_direction: Literal["L2R","R2L","neutral"] = "neutral"
    intensity: float = 0.5        # 0..1 from the arc model
    target_duration_s: float = 2.5
    avoid_clip_ids: list[str] = []
```

### 3. ClipRecord (`cinema/clip.py`)

Superset shape with **nullable embedding/scale/move/caption/luminance/etc.** so
Plan B backfills. Plan A fills only the fields available from provider
responses (source, url, duration, w/h, caption/alt/tags, preview_url).

```python
class ClipRecord(BaseModel):
    clip_id: str
    provider: Literal["pexels","pixabay","local","generative"]
    source_url: str; local_path: str | None
    duration_s: float; width: int | None; height: int | None
    embedding: list[float] | None = None
    caption: str | None = None
    scale: ShotScale | None = None
    move: CameraMove | None = None
    palette: list[str] | None = None
    luminance: float | None = None
    motion_energy: float | None = None
    faces: int | None = None
    average_hash: str | None = None      # Pillow/numpy average/perceptual hash of preview thumbnails
    used_in_video_ids: list[str] = []
```

### 4. Director (`cinema/director_service.py`)
**LLM-first with a first-class deterministic fallback** (amended):

- `LLM_DIRECTOR_*` behind `CINEMA_DIRECTOR_ENABLED` flag (default off, tests
  pass without LLM).
- Per scene: build `ShotSpec[]` + `scene_mode` + `pacing` curve from
  `parse_screenplay()` + narration. **Hard concrete-subject rule**: the prompt
  forbids abstract nouns and requires rewriting them ("wealth" → "stack of
  coins"). Reuses the existing `/footage`-agnostic LLM path with key rotation.
- **Cache**: SQLite table keyed on `hash(scene_text + director_version)` so a
  re-render doesn't burn quota. Invasive change is owned by `cinema/cache.py`.
- **Never blocks a render** (enforced by test): 1 LLM call; on 429/402/error →
  one retry via key rotation with a hard timeout (config `CINEMA_DIRECTOR_TIMEOUT_S`,
  default 8s) → on any failure, use `deterministic_director(scene)`.
- `deterministic_director` is a pure function: keyword→scale map ("face"/"close"
  → CU; "room"/"stage" → MS; "crowd"/"city"/"skyline" → LS/ELS), move defaults
  to STATIC, function inferred from position (first=ESTABLISH, last=PAYOFF),
  fixed pacing (ASL 2.5s, intensity from a linear arc). Fully testable with no
  network.
- Log `director_source` per scene: `inferred` | `deterministic` | `cached`.

### 5. Deterministic scorer (`cinema/scorer.py`)

Replaces the pure-text `_rerank_candidates` path (kept for fallback under flag).

```
score(c, spec, prev) =
    w1 * semantic(c, spec)                  # embedding if present; else text-sim via captions
  + w2 * typed_match(c, spec)               # scale/move/function; None fields = NEUTRAL (0), never mismatch
  + w3 * neighbor_term(c, prev, mode)       # tonal continuity or deliberate contrast
  + w4 * quality(c)                         # res >= 1080, dur >= target, no watermark
  - w5 * similarity_to_selected(c)          # MMR; average_hash dedup, threshold Hamming <= 6
  - w6 * usage_penalty(c)                   # used_in_video_ids cooldown
```

Key rules (amended):
- **None typed fields are neutral** (weight 0), never scored as a mismatch.
- **Dedup mechanism PINNED**: average/perceptual hash on provider **preview
  thumbnails** via Pillow/numpy (deps already present). Hamming distance ≤ 6 →
  `reject`. This is explicit and image-derived — **not** URL or provider-ID
  matching, which is explicitly disallowed (a clip can appear under two IDs or
  two URLs and must be deduped). `average_hash` field stores the hex digest.
- Weights are per-mode config in `cinema/modes.py` (dict of MontageMode → config).

### 6. Integration (`stock_footage_service.py`)

- New entry `rerank_with_cinema(all_videos, spec, prev_clip)` called when
  `CINEMA_ENABLED`. Build `ClipRecord`s from provider results, run scorer, fall
  back to existing text path if the cinema path raises or returns nothing.
- `script_parsing_service.py`: keep `camera`/`action` blocks (already typed at
  lines 111-114); add a `to_shotspec()` helper instead of `extract_shot_descriptions`
  flattening.

## Config (`cinema/` additions to `.env.example`)

```
CINEMA_ENABLED=false
CINEMA_DIRECTOR_ENABLED=false
CINEMA_DIRECTOR_TIMEOUT_S=8
CINEMA_DIRECTOR_MODEL=            # default: SCRIPT_MODEL or gpt-4o-mini
CINEMA_ASL_BASE=2.5
CINEMA_DEDUP_HAMMING=6
```

## Acceptance

- `deterministic_director` returns valid ShotSpec[] for the real 12-scene script
  (unit test, no network).
- Scorer rejects an average-hash-duplicate clip; treats a None-scale candidate
  as neutral, not mismatch.
- `never blocks a render` enforced by a test that stubs LLM to always fail and
  asserts the deterministic path produces a plan.
- Existing test suite passes with `CINEMA_ENABLED=false` (all new deps absent).

## Non-goals

- No embeddings, no torch, no pgvector, no footage ingest in Plan A.
- No ComfyUI/Wan changes; no TTS/caption/uploader changes.
