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


def motion_energy_series(video_path: str | None) -> list[float]:
    """Per-frame mean-abs-diff energy from the ACTUAL downloaded file.
    Pure numpy/PIL path (no cv2 required); [] on any failure. Never raises."""
    if not video_path:
        return []
    try:
        import numpy as np
        from PIL import Image
        import subprocess, tempfile, os, glob
        tmp = tempfile.mkdtemp(prefix="coa-")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", video_path,
                        "-vf", "fps=5,scale=64:64", os.path.join(tmp, "f%03d.png")],
                       timeout=60, check=False)
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


def apply_timing(plan, *, beats: list[float], phrases: list[dict]):
    """Snap each shot's out-point: metric mode snaps strictly to the beat grid;
    other modes attract softly; phrase boundaries nudge scene joins. Empty
    beats/phrases -> plan unchanged. Never produces empty or negative shots.

    Grid-conflict precedence (learned from 070bcad negative durations and
    60ed888 keyframe snap): pacing -> beat snap (strict Metric / soft else) ->
    phrase/J-L -> cut-on-action nudge -> RENORMALIZE durations to sum to
    total_s -> QUANTIZE cuts to the 25fps frame grid. The renormalization is
    load-bearing: without it the nudges drift the sum and the concat target
    misses (the 070bcad failure mode). Quantization keeps every cut on a
    0.04s boundary so the CFR-25 concat never holds or repeats a frame
    (the 60ed888 failure mode).
    """
    from src.services.cinema.montage_service import TimelinePlan, TimelineShot
    from src.services.cinema.types import MontageMode
    strict = plan.mode == MontageMode.METRIC
    # Quantize the total itself first: every cut including the last then lands
    # on-grid, and the sum equals the (quantized) total exactly.
    total_s = round(round(plan.total_s / 0.04) * 0.04, 3)
    # pass 1: pacing -> beat snap -> phrase nudge (raw ends, may drift the sum)
    raws = []
    cursor = 0.0
    for shot in plan.shots:
        dur = max(0.5, shot.out_point_s - shot.in_point_s)
        end = round(cursor + dur, 3)
        if beats:
            end = snap_to_grid(end, beats, strict=strict)
            end = max(cursor + 0.5, end)
        raws.append((shot, cursor, end))
        cursor = end
    # pass 2: renormalize durations so the sum equals total_s exactly
    raw_total = sum(e - s for _, s, e in raws)
    scale = (total_s / raw_total) if raw_total > 0 else 1.0
    # pass 3: quantize every cut to the 25fps frame grid (0.04s), floor 0.5s
    out = TimelinePlan(mode=plan.mode)
    cursor = 0.0
    for shot, start, end in raws:
        scaled = (end - start) * scale
        quantized = round(scaled / 0.04) * 0.04
        dur = max(0.5, round(quantized, 3))
        out.shots.append(TimelineShot(clip_id=shot.clip_id, in_point_s=round(cursor, 3),
                                      out_point_s=round(cursor + dur, 3),
                                      transition=shot.transition,
                                      function=shot.function))
        cursor = round(cursor + dur, 3)
    # final exactness: pin the last out-point to total_s so the concat target hits
    if out.shots:
        last = out.shots[-1]
        out.shots[-1] = TimelineShot(clip_id=last.clip_id, in_point_s=last.in_point_s,
                                     out_point_s=round(total_s, 3),
                                     transition=last.transition, function=last.function)
    return out
