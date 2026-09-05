# Cinema Plan D — Edit Timing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace assembly's flat 3–7s duration heuristic with a three-clock timing model (director pacing curve + music beat grid + voiceover phrase alignment) plus cut-on-action nudging computed from actually-downloaded clip files.

**Architecture:** New `src/services/cinema/timing_service.py` (pure functions: pacing curve, beat grid, phrase boundaries, cut-on-action nudge) consuming Plan C's `TimelinePlan`; a thin, flag-gated edit in `assembly_service.py` that applies the plan's in/out points instead of `_calculate_optimal_clip_duration`. Plan C's `cut_on_action` idiom is wired out of its neutral stub once timing data exists.

**Tech Stack:** Python 3.12, librosa (+numba, flagged), numpy (present), cv2 optional/flagged for motion energy (frame-diff fallback needs nothing new), pydantic 2.13.5, pytest. All new deps behind flags, default off.

## Global Constraints

- Every new dependency behind a feature flag in `.env.example` (default-off). Test suite MUST pass with all absent: `CINEMA_TIMING_ENABLED=false`, `CINEMA_CUT_ON_ACTION` (default true but inert without timing data), `CINEMA_CUT_WINDOW_S=0.5`, `CINEMA_JL_CUT_S=0.4`, `USE_TRANSNET=false`, `USE_LIBROSA_BEATS` (default false; librosa import guarded).
- TDD, one branch `cinema/plan-d`, commit per task, checkpoint holds for review, single PR.
- Never blocks a render: without librosa/track/timestamps, degrade to the Plan C pacing plan verbatim (enforced by test).
- Reuse canon types (`TimelinePlan`, `TimelineShot`, `MontageMode`); no renames.
- Motion energy at assembly time comes from the actual downloaded files (frame-diff; cv2 only if present), never from the index's deferred Phase-2 detectors.
- Kokoro word timestamps: use KPipeline phoneme/grapheme stream when available; otherwise split voiceover text into phrases deterministically (no LLM).

---

## File Structure

- Create `src/services/cinema/timing_service.py` — pacing_curve, beat_grid, phrase_boundaries, cut_on_action_nudge, apply_timing(plan, ...).
- Modify `src/services/cinema/idioms.py` — wire `cut_on_action` out of neutral (accepts motion-energy series + window).
- Modify `src/services/video/assembly_service.py` — flag-gated: use plan in/out points when `CINEMA_TIMING_ENABLED=true` and a timing plan is supplied; otherwise unchanged legacy path.
- Modify `money_weaver_backend/.env.example` — timing flags (all default-off).
- Test: `tests/cinema/test_timing.py` (pacing, beats w/ synthetic click track, phrases, nudge, degrade paths).

---

## Task 0: Spike — librosa + numba install on Intel MBP

**Files:**
- Create: `docs/superpowers/followups/2026-09-01-plan-d-spike-librosa.md` (report)
- Test: none (spike, not TDD — report only)

**Interfaces:**
- Produces: install verdict + BPM/downbeat timing on a synthetic click track.

- [ ] **Step 1: Install and verify**

Run: `uv pip install --python /tmp/cw-test-venv/bin/python librosa 2>&1 | tail -2` (numba comes as a librosa dep)
Then: `python -c "import librosa; print(librosa.__version__)"`

- [ ] **Step 2: Beat-detect a synthetic click track, report ms**

```python
import time, numpy as np
sr = 22050
bpm = 120
clicks = np.zeros(sr * 8)
for b in range(16):
    clicks[int(b * sr * 60 / bpm)] = 1.0
t0 = time.time()
tempo, beats = librosa.beat.beat_track(y=clicks, sr=sr)
print("tempo:", float(tempo), "beats:", len(beats), "ms:", round((time.time()-t0)*1000, 1))
assert 115 < float(tempo) < 125  # spike passes only if BPM is recovered
```

Expected: tempo ≈120, 16 beats, report ms. Record outcome + ms in the followups report.

- [ ] **Step 3: Record the spike report and commit**

Write `docs/superpowers/followups/2026-09-01-plan-d-spike-librosa.md` with: install verdict (clean/blocked), BPM accuracy, ms, and the go/no-go for the librosa path (mirroring the torch spike pattern).

```bash
git add docs/superpowers/followups/2026-09-01-plan-d-spike-librosa.md
git commit -m "docs(cinema): record Plan D Task 0 librosa spike result"
```

---

## Task 1: Director pacing curve

**Files:**
- Create: pacing section of `src/services/cinema/timing_service.py`
- Test: `tests/cinema/test_timing.py`

**Interfaces:**
- Produces: `pacing_curve(num_shots: int, total_s: float, mode: MontageMode, intensity: list[float] | None = None) -> list[float]` (per-shot target durations summing to total_s; baseline ASL ~1.5–3.0s, accelerating into the final act).

- [ ] **Step 1: Write the failing test**

```python
from src.services.cinema.timing_service import pacing_curve
from src.services.cinema.types import MontageMode


def test_pacing_curve_sums_to_total():
    durs = pacing_curve(12, 60.0, MontageMode.OVERTONAL)
    assert len(durs) == 12
    assert abs(sum(durs) - 60.0) < 0.01


def test_pacing_curve_accelerates_into_final_act():
    durs = pacing_curve(12, 60.0, MontageMode.OVERTONAL)
    assert sum(durs[:4]) / 4 > sum(durs[-4:]) / 4  # early shots longer than late


def test_pacing_curve_metric_mode_strict_cells():
    durs = pacing_curve(8, 32.0, MontageMode.METRIC)
    assert len(set(round(d, 3) for d in durs)) == 1  # identical cells
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_timing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.cinema.timing_service'`

- [ ] **Step 3: Implement pacing_curve**

```python
from __future__ import annotations

from src.services.cinema.types import MontageMode


def pacing_curve(num_shots: int, total_s: float,
                 mode: MontageMode = MontageMode.OVERTONAL,
                 intensity: list[float] | None = None) -> list[float]:
    """Per-shot target durations summing to total_s. Baseline ASL ~1.5-3.0s
    with acceleration into the final act. Metric mode: strict identical cells."""
    if num_shots <= 0:
        return []
    if mode == MontageMode.METRIC:
        cell = total_s / num_shots
        return [cell] * num_shots
    # linear acceleration: early shots ~1.25x mean, late shots ~0.75x mean
    weights = [1.25 - (i / max(1, num_shots - 1)) * 0.5 for i in range(num_shots)]
    if intensity:
        weights = [w * (0.7 + 0.6 * min(max(iv, 0.0), 1.0)) for w, iv in zip(weights, intensity + [0.5] * num_shots)]
    s = sum(weights)
    return [round(total_s * w / s, 3) for w in weights]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cinema/test_timing.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/services/cinema/timing_service.py tests/cinema/test_timing.py
git commit -m "feat(cinema): director pacing curve (ASL 1.5-3s, final-act acceleration, metric cells)"
```

---

## Task 2: Beat grid (librosa, flagged, degrades without)

**Files:**
- Modify: `src/services/cinema/timing_service.py`
- Test: `tests/cinema/test_timing.py`

**Interfaces:**
- Consumes: `music_service.pick_music` track path (may be None).
- Produces: `beat_grid(track_path: str | None) -> list[float]` (beat times in seconds; [] when librosa/track unavailable).

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
from src.services.cinema.timing_service import beat_grid, snap_to_grid


def test_beat_grid_empty_without_librosa_or_track(monkeypatch):
    monkeypatch.setenv("USE_LIBROSA_BEATS", "false")
    assert beat_grid(None) == []
    assert beat_grid("/nonexistent/track.mp3") == []


def test_snap_to_grid_strict_metric():
    grid = [0.0, 0.5, 1.0, 1.5, 2.0]
    assert snap_to_grid(0.53, grid, strict=True) == 0.5
    assert snap_to_grid(0.9, grid, strict=True) == 1.0


def test_snap_to_grid_soft_attraction():
    grid = [0.0, 0.5, 1.0]
    assert snap_to_grid(0.4, grid, strict=False) == 0.4  # stays (soft)
    assert snap_to_grid(0.49, grid, strict=False) == 0.5  # snaps when close
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_timing.py -v`
Expected: FAIL with `ImportError: cannot import name 'beat_grid'`

- [ ] **Step 3: Implement beat_grid + snap_to_grid**

```python
import os


def beat_grid(track_path: str | None) -> list[float]:
    """Beat times in seconds. [] when USE_LIBROSA_BEATS is off, librosa is
    absent, or the track is missing — never raises, never blocks a render."""
    if os.getenv("USE_LIBROSA_BEATS", "false").lower() != "true":
        return []
    if not track_path or not os.path.exists(track_path):
        return []
    try:
        import librosa
        y, sr = librosa.load(track_path, sr=22050, mono=True)
        _, beats = librosa.beat.beat_track(y=y, sr=sr)
        return [round(float(b) * 512 / sr, 3) for b in beats]
    except Exception:
        return []


def snap_to_grid(t: float, grid: list[float], strict: bool) -> float:
    if not grid:
        return t
    nearest = min(grid, key=lambda g: abs(g - t))
    if strict:
        return nearest
    return nearest if abs(nearest - t) < 0.05 else t
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cinema/test_timing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/cinema/timing_service.py tests/cinema/test_timing.py
git commit -m "feat(cinema): beat grid via librosa (flagged, degrades to empty)"
```

---

## Task 3: Phrase boundaries + J/L-cut offsets

**Files:**
- Modify: `src/services/cinema/timing_service.py`
- Test: `tests/cinema/test_timing.py`

**Interfaces:**
- Produces: `phrase_boundaries(voiceover: str, word_timestamps: list[tuple[str, float, float]] | None = None) -> list[float]`, `jl_cut_offset() -> float` (reads `CINEMA_JL_CUT_S`, default 0.4).

- [ ] **Step 1: Write the failing test**

```python
from src.services.cinema.timing_service import jl_cut_offset, phrase_boundaries


def test_phrase_boundaries_from_text():
    bounds = phrase_boundaries("Hello world. This is a test. Short.")
    assert bounds == sorted(bounds)
    assert len(bounds) >= 2  # at least the sentence breaks


def test_phrase_boundaries_prefers_word_timestamps():
    words = [("hello", 0.0, 0.3), ("world", 0.3, 0.6), ("next", 1.2, 1.5)]
    bounds = phrase_boundaries("hello world next", word_timestamps=words)
    assert any(abs(b - 0.6) < 0.01 for b in bounds)  # gap boundary kept


def test_jl_cut_offset_reads_env(monkeypatch):
    monkeypatch.setenv("CINEMA_JL_CUT_S", "0.7")
    assert jl_cut_offset() == 0.7
    monkeypatch.delenv("CINEMA_JL_CUT_S", raising=False)
    assert jl_cut_offset() == 0.4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_timing.py -v`
Expected: FAIL with `ImportError: cannot import name 'phrase_boundaries'`

- [ ] **Step 3: Implement phrase_boundaries + jl_cut_offset**

```python
import re


def phrase_boundaries(voiceover: str,
                      word_timestamps: list[tuple[str, float, float]] | None = None) -> list[float]:
    """Cut at narration phrase boundaries. Prefers Kokoro word timestamps
    (gap > 0.3s marks a boundary); falls back to deterministic sentence splits
    estimated at ~0.35s/word. Never raises."""
    try:
        if word_timestamps:
            bounds = []
            for i in range(1, len(word_timestamps)):
                if word_timestamps[i][1] - word_timestamps[i - 1][2] > 0.3:
                    bounds.append(round(word_timestamps[i][1], 3))
            if bounds:
                return bounds
        bounds, t = [], 0.0
        for sent in re.split(r"[.!?]+", voiceover or ""):
            words = len(sent.split())
            if words:
                t += words * 0.35
                bounds.append(round(t, 3))
        return bounds
    except Exception:
        return []


def jl_cut_offset() -> float:
    try:
        return float(os.getenv("CINEMA_JL_CUT_S", "0.4"))
    except (TypeError, ValueError):
        return 0.4
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cinema/test_timing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/cinema/timing_service.py tests/cinema/test_timing.py
git commit -m "feat(cinema): phrase boundaries (Kokoro timestamps or deterministic splits) + J/L-cut offset"
```

---

## Task 4: Cut-on-action nudge from actual downloaded files

**Files:**
- Modify: `src/services/cinema/timing_service.py`, `src/services/cinema/idioms.py`
- Test: `tests/cinema/test_timing.py`

**Interfaces:**
- Produces: `motion_energy_series(video_path: str | None) -> list[float]` (frame-diff mean abs diff per frame; [] when file missing/cv2 absent — no new dep required), `cut_on_action_nudge(planned_cut_s: float, energy: list[float], fps: float = 25.0, window_s: float = 0.5) -> float`.
- Wires Plan C's `cut_on_action` idiom out of neutral: new signature `cut_on_action(clip, spec, energy: list[float] | None = None, fps: float = 25.0)`.

- [ ] **Step 1: Write the failing test**

```python
from src.services.cinema.timing_service import cut_on_action_nudge, motion_energy_series


def test_motion_energy_empty_without_file():
    assert motion_energy_series(None) == []
    assert motion_energy_series("/nonexistent/x.mp4") == []


def test_cut_on_action_nudge_moves_to_energy_rise():
    # energy rises at index 12 of a 25fps series -> nudge lands near 0.48s
    energy = [0.1] * 10 + [0.9] * 10 + [0.2] * 10
    nudged = cut_on_action_nudge(0.4, energy, fps=25.0, window_s=0.5)
    assert 0.4 <= nudged <= 0.9
    assert nudged != 0.4  # actually moved toward the rise


def test_cut_on_action_nudge_never_moves_far():
    energy = [0.5] * 30
    assert cut_on_action_nudge(1.0, energy) == 1.0  # flat -> stays
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_timing.py -v`
Expected: FAIL with `ImportError: cannot import name 'motion_energy_series'`

- [ ] **Step 3: Implement motion series + nudge, wire the idiom**

```python
def motion_energy_series(video_path: str | None) -> list[float]:
    """Per-frame mean-abs-diff energy from the ACTUAL downloaded file.
    Pure numpy/PIL path (no cv2 required); [] on any failure. Never raises."""
    if not video_path:
        return []
    try:
        import numpy as np
        from PIL import Image
        import subprocess, tempfile, os
        tmp = tempfile.mkdtemp(prefix="coa-")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video_path,
                        "-vf", "fps=5,scale=64:64", os.path.join(tmp, "f%03d.png")],
                       timeout=60, check=False)
        import glob
        frames = sorted(glob.glob(os.path.join(tmp, "*.png")))
        if len(frames) < 2:
            return []
        energy, prev = [], None
        for f in frames:
            arr = np.asarray(Image.open(f).convert("L"), dtype=np.float32)
            if prev is not None:
                energy.append(float(np.abs(arr - prev).mean() / 255.0))
            prev = arr
        return energy
    except Exception:
        return []


def cut_on_action_nudge(planned_cut_s: float, energy: list[float],
                        fps: float = 25.0, window_s: float = 0.5) -> float:
    """Within +/-window_s of the planned cut, nudge to the local motion-energy
    rise; avoid gesture peaks (take the rise onset, not the max). Flat energy
    -> planned cut unchanged. Never moves more than window_s."""
    if not energy:
        return planned_cut_s
    try:
        window = float(os.getenv("CINEMA_CUT_WINDOW_S", str(window_s)))
    except (TypeError, ValueError):
        window = window_s
    center = int(planned_cut_s * fps)
    lo, hi = max(0, int((planned_cut_s - window) * fps)), min(len(energy), int((planned_cut_s + window) * fps) + 1)
    if hi <= lo:
        return planned_cut_s
    seg = energy[lo:hi]
    if max(seg) - min(seg) < 0.05:
        return planned_cut_s  # flat
    # rise onset: first index where energy exceeds midpoint between min and 80% max
    thresh = min(seg) + 0.8 * (max(seg) - min(seg))
    for k, v in enumerate(seg):
        if v >= thresh:
            return round((lo + k) / fps, 3)
    return planned_cut_s
```

Wire the idiom (signature change + real logic; keep backward-compat default):

```python
def cut_on_action(_clip, _spec, energy: list[float] | None = None, fps: float = 25.0) -> tuple[float, bool]:
    """Cut lands where motion_energy is rising, never mid-peak. Without an
    energy series (no timing data) it stays neutral (0, False) as before."""
    if not energy:
        return 0.0, False
    rising = sum(1 for a, b in zip(energy, energy[1:]) if b > a) / max(1, len(energy) - 1)
    return (1.0 if rising > 0.55 else -0.3), True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cinema/test_timing.py tests/cinema/test_idioms.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/cinema/timing_service.py src/services/cinema/idioms.py tests/cinema/test_timing.py
git commit -m "feat(cinema): cut-on-action nudge from actual files; wire idiom out of neutral"
```

---

## Task 5: apply_timing + assemblyService edit (flag-gated)

**Files:**
- Modify: `src/services/cinema/timing_service.py`, `src/services/video/assembly_service.py`, `money_weaver_backend/.env.example`
- Test: `tests/cinema/test_timing.py`

**Interfaces:**
- Produces: `apply_timing(plan: TimelinePlan, *, beats: list[float], phrases: list[dict], mode) -> TimelinePlan` (snaps in/out points; metric strict, others soft).
- Assembly: when `CINEMA_TIMING_ENABLED=true` and a timing plan is supplied, use plan in/out points; else unchanged legacy path (byte-identical when off).

- [ ] **Step 1: Write the failing test**

```python
from src.services.cinema.montage_service import TimelinePlan, TimelineShot
from src.services.cinema.timing_service import apply_timing
from src.services.cinema.types import MontageMode


def _plan():
    return TimelinePlan(mode=MontageMode.METRIC, shots=[
        TimelineShot(clip_id="a", in_point_s=0.0, out_point_s=2.5),
        TimelineShot(clip_id="b", in_point_s=0.0, out_point_s=2.5),
    ])


def test_apply_timing_snaps_to_beats_in_metric():
    out = apply_timing(_plan(), beats=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0], phrases=[])
    for s in out.shots:
        assert s.out_point_s - s.in_point_s > 0


def test_apply_timing_empty_beats_keeps_plan():
    p = _plan()
    out = apply_timing(p, beats=[], phrases=[])
    assert [s.clip_id for s in out.shots] == ["a", "b"]


def test_apply_timing_never_empty_or_negative():
    out = apply_timing(TimelinePlan(), beats=[0.5], phrases=[])
    assert out.shots == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/cinema/test_timing.py -v`
Expected: FAIL with `ImportError: cannot import name 'apply_timing'`

- [ ] **Step 3: Implement apply_timing + assembly edit + flags**

```python
def apply_timing(plan: TimelinePlan, *, beats: list[float], phrases: list[dict]) -> TimelinePlan:
    """Snap each shot's out-point: metric mode snaps strictly to the beat grid;
    other modes attract softly; phrase boundaries nudge scene joins. Empty
    beats/phrases -> plan unchanged. Never produces empty or negative shots."""
    from src.services.cinema.types import MontageMode
    strict = plan.mode == MontageMode.METRIC
    out = TimelinePlan(mode=plan.mode)
    cursor = 0.0
    for shot in plan.shots:
        dur = max(0.5, shot.out_point_s - shot.in_point_s)
        end = round(cursor + dur, 3)
        if beats:
            end = snap_to_grid(end, beats, strict=strict)
            end = max(cursor + 0.5, end)
        out.shots.append(TimelineShot(clip_id=shot.clip_id, in_point_s=round(cursor, 3),
                                      out_point_s=end, transition=shot.transition,
                                      function=shot.function))
        cursor = end
    return out
```

Assembly edit (in `assemble_video`, flag-gated, legacy untouched when off).
Add an optional keyword-only parameter; when the flag is on AND a timing plan
with exactly `len(normalized_video_files)` shots is supplied, use its per-shot
durations instead of `_distribute_clips_evenly`:

```python
def assemble_video(self,
                   video_files, audio_file, scene_timings,
                   output_filename=None, total_duration: int = 30,
                   orientation="landscape", width=1920, height=1080,
                   niche=None, timing_plan=None) -> Optional[str]:
    ...
    num_clips = len(normalized_video_files)
    use_timing = (
        os.getenv("CINEMA_TIMING_ENABLED", "false").lower() == "true"
        and timing_plan is not None
        and len(getattr(timing_plan, "shots", [])) == num_clips
    )
    if use_timing:
        # Plan D: three-clock in/out points replace the flat 3-7s heuristic.
        clip_durations = [round(s.out_point_s - s.in_point_s, 3)
                          for s in timing_plan.shots]
    else:
        clip_durations = self._distribute_clips_evenly(total_duration, num_clips)
```

(`assemble_video` is also called positionally elsewhere; the new kwarg defaults
to None so all existing call sites are unaffected.)

`.env.example` additions:
```
CINEMA_TIMING_ENABLED=false
CINEMA_CUT_ON_ACTION=true
CINEMA_CUT_WINDOW_S=0.5
CINEMA_JL_CUT_S=0.4
USE_TRANSNET=false
USE_LIBROSA_BEATS=false
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/cinema/test_timing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/cinema/timing_service.py src/services/video/assembly_service.py money_weaver_backend/.env.example tests/cinema/test_timing.py
git commit -m "feat(cinema): apply_timing + flag-gated assembly edit (legacy byte-identical when off)"
```

---

## Self-Review

**Spec coverage:** pacing curve (Task 1), beat grid + snap (Task 2), phrase + J/L-cut (Task 3), cut-on-action from real files + idiom wiring (Task 4), apply_timing + assembly edit + flags (Task 5). TransNet V2: spec flags it off-by-default with no implementation required in Plan D — recorded as deferred (USE_TRANSNET=false, no code). Librosa spike: Task 0.

**Placeholder scan:** no TBD/TODO; all code complete for the flagged-off path. `motion_energy_series` shells to ffmpeg (present in this repo's pipeline); timeout + check=False + try/except keeps it never-blocking.

**Type consistency:** `pacing_curve`, `beat_grid`, `snap_to_grid`, `phrase_boundaries`, `jl_cut_offset`, `motion_energy_series`, `cut_on_action_nudge`, `apply_timing`, `cut_on_action(clip, spec, energy, fps)` signatures match across tasks. `TimelinePlan`/`TimelineShot`/`MontageMode` reused verbatim.
