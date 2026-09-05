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
