from __future__ import annotations

import os

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


def phrase_boundaries(voiceover: str,
                      word_timestamps: list[tuple[str, float, float]] | None = None) -> list[float]:
    """Cut at narration phrase boundaries. Prefers Kokoro word timestamps
    (gap > 0.3s marks a boundary); falls back to deterministic sentence splits
    estimated at ~0.35s/word. Never raises."""
    import re
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
