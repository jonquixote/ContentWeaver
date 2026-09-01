# Cinema Plan D — Edit Timing

Date: 2026-08-31
Status: Design (pre-implementation)
Scope: `money_weaver_backend/src/services/cinema/timing_service.py` + `assembly_service.py` edit.
Depends on Plan C (`TimelinePlan`). Adds `librosa` behind flag.

## Problem

Assembly applies a 3–7s duration heuristic; cuts are arbitrary, not on the
music beat or narration phrase.

## Design

- **Beat grid** (`timing_service.beat_grid`): librosa BPM/downbeat detection on
  the `music_service` track. Metric mode: strict cells (cuts snap to beat).
  Other modes: soft attraction.
- **Phrase alignment**: Kokoro word timestamps → cut at narration phrase
  boundaries; J-cut/L-cut offsets ±0.3–0.8s at scene joins.
- **Cut-on-action**: within a ±0.5s window around the planned cut, nudge to a
  local motion-energy rise; avoid gesture peaks.
- Slicing long stock clips into sub-shots: run TransNet V2 first (so a "clip"
  is a real shot) — flagged `USE_TRANSNET`, off by default.
- If librosa/audio unavailable, degrade to Plan C's pacing plan verbatim
  (never blocks a render; enforced by test).

## Config

```
CINEMA_TIMING_ENABLED=false
CINEMA_CUT_ON_ACTION=true
CINEMA_CUT_WINDOW_S=0.5
CINEMA_JL_CUT_S=0.4
USE_TRANSNET=false
```

## Acceptance

- Metric mode: cuts within ±1 frame of the beat grid (hosted test).
- Phrase-boundary alignment ≥85% when Kokoro timestamps present.
- Without librosa/track, falls back to the Plan C plan (unit test).

## Non-goals

- No TTS voice changes; no caption rendering; no music generation.
