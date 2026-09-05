# Plan D Task 0 spike — librosa + numba on Intel MBP (2026-09-04)

## Result: BLOCKED in this environment

- `uv pip install librosa` resolves numba 0.67.0 + llvmlite 0.49.0, which have
  **no prebuilt wheel for Python 3.13 on this macOS target** — pip falls back
  to source build, which requires LLVM (`find_package(LLVM)` via cmake).
- No LLVM present (`llvm-config` missing, no brew llvm). Building LLVM from
  source is out of scope for the spike.
- BPM/downbeat timing therefore **not verified** here. No ms number to report.

## Implication (designed degradation, not a plan blocker)

- `USE_LIBROSA_BEATS` defaults false; `beat_grid()` returns [] without librosa
  or a track — tested and enforced. Metric mode still yields strict identical
  cells from the pacing curve (durations snap to equal cells, just not to
  audio beats).
- The acceptance ritual's "cuts within ±1 frame of the beat grid" criterion
  **cannot run in this env**; it needs a box with librosa (CI with linux
  wheels, or `brew install llvm` + rebuild here). Recorded as a Plan D
  follow-up, not a gate failure — the pacing/phrase/cut-on-action clocks all
  work without it.

## Go/no-go

GO for Tasks 1-5 (all implementable + testable without librosa). Beat-grid
behavior is fully covered by the degrade-to-empty contract and the
snap_to_grid unit tests (synthetic grids, no audio needed).

## Follow-ups logged from Plan D review (2026-09-04)

- **Pure-numpy spectral-flux beat tracker**: restore the beat clock without
  librosa/LLVM. Implement onset-envelope + tempo estimation in numpy
  (spectral flux on STFT magnitudes, autocorrelation tempo) behind the same
  `USE_LIBROSA_BEATS` flag path (rename to a backend-agnostic flag when both
  exist). Acceptance: same ±1-frame beat-grid test against a synthetic click
  track. This unblocks the Metric-mode beat criterion in this env.
- **Two-venv reality in env docs**: backend runs Python 3.13 (no torch, no
  librosa wheels), ML work runs Python 3.12 (`/tmp/cw-test-venv`-style venv
  with torch 2.2.2 + numpy<2). Record in env docs which venv owns which
  capability so future spikes don't rediscover it.
