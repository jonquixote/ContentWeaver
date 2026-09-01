# Cinema Plan C — Montage Planner + Idiom Library

Date: 2026-08-31
Status: Design (pre-implementation)
Scope: `money_weaver_backend/src/services/cinema/montage_service.py` + `modes.py`.
Depends on Plan A (`ShotSpec`) and Plan B (`ClipRecord`). Pure logic, no deps.

## Goal

Consume ordered `ShotSpec[]` + candidate `ClipRecord[]` and produce a
**timeline plan** (clip_id, in/out points, transition) per shot, under a chosen
MontageMode + pacing curve. Replaces the per-query "try terms until we find
videos" loop.

## Montage modes as objective functions (`cinema/modes.py`)

| Mode | Mechanism | Scorer effect |
|---|---|---|
| Metric | Fixed-formula cells; progressive shortening | durations from formula; w3-rhythm → 0 |
| Rhythmic | Cut when motion/gesture completes; length ∝ motion_energy | w4-motion, rhythmic durations |
| Tonal | Match palette/luminance/mood across join | w3-palette/luma raised |
| Overtonal (default) | All weighted together | balanced weights |
| Intellectual | Adjacent shots must differ on a typed axis | w3 inverted (contrast penalty) |

Each mode = a `ModeConfig` (dict of weights). Exposed at `montage_service.MODES`.

## Editing idioms (`cinema/idioms.py`)

Scored soft constraints, each returns `(bonus|penalty, applied_bool)`:

- **Peaks+valleys**: CU when intensity high, LS when low, MS mid.
- **Progressive scale**: prefer LS→MS→CU; big jumps penalized unless Intellectual.
- **Screen-direction continuity**: consecutive movement shots share direction.
- **Cut on action**: cut lands where motion_energy rising, never mid-peak.
- **Hold reaction**: after PAYOFF, hold 0.5–1.0s before next cut.
- **No repeat subject**: embedding/hash sim to any selected > threshold → reject.
- **Establish first**: scene opens with ESTABLISH (LS/ELS) unless cold-open.

## Planner (`montage_service.py`)

```
plan(shot_specs, candidates) -> TimelinePlan
```

- For each ShotSpec, `score(c, spec, prev)` from Plan A scorer, MMR-iterate.
- Apply active mode config + soft idioms (weighted sum into the score).
- Emit `TimelineShot(clip_id, in_point_s, out_point_s, transition, function)`.
- Guarantees: scene never empty (fall back to best-quality eligible clip);
  dedup across whole video (Plan A hash); a `TimelinePlan` always produced even
  with empty input (graceful empty plan).

## Acceptance

- Pure-logic unit tests for each mode objective (no network).
- Progressive-scale idiom promotes LS→MS→CU ordering; Intellectual inverts it.
- Empty-candidate input yields an empty plan (no exception).
- Cross-scene dedup at video level enforced (no clip reused).

## Non-goals

- No beat-grid/audio timing (Plan D). No VLM critic (Plan E). No ingest (Plan B).
