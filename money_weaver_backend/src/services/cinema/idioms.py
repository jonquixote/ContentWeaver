from __future__ import annotations

from src.services.cinema.clip import ClipRecord
from src.services.cinema.scorer import dedup_reject
from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import CameraMove, MontageMode, ShotFunction, ShotScale


def peaks_and_valleys(clip: ClipRecord, spec: ShotSpec) -> tuple[float, bool]:
    """CU when intensity high, LS when low, MS mid. Returns (bonus, applied)."""
    if spec.scale is None or clip.scale is None:
        return 0.0, False
    # ideal scale for the intensity: CU for hi, LS for lo, MS mid.
    ideal = ShotScale.CU if spec.intensity > 0.66 else (ShotScale.MS if spec.intensity > 0.33 else ShotScale.LS)
    if clip.scale == ideal:
        return 1.0, True
    if shot_scale_index(clip.scale) == shot_scale_index(ideal) - 1 or shot_scale_index(clip.scale) == shot_scale_index(ideal) + 1:
        return 0.4, True  # adjacent scale — mild
    return -0.5, True  # far off the ideal


def shot_scale_index(s: ShotScale | None) -> int:
    order = {"ecu": 0, "cu": 1, "mcu": 2, "ms": 3, "mls": 4, "ls": 5, "els": 6, "abstract": 7}
    return order.get(s.value if s else "ms", 3)


def progressive_scale(clip: ClipRecord, spec: ShotSpec, mode: MontageMode) -> tuple[float, bool]:
    """Prefer LS->MS->CU progression; big jumps penalized UNLESS Intellectual
    (which rewards juxtaposition/contrast). Returns (bonus, applied)."""
    if clip.scale is None or spec.scale is None:
        return 0.0, False
    if mode == MontageMode.INTELLECTUAL:
        # reward contrast: further from the shot's scale is better
        diff = abs(shot_scale_index(clip.scale) - shot_scale_index(spec.scale))
        return float(diff), True
    # progressive: closer to the shot's scale is "on the progression" -> better
    diff = abs(shot_scale_index(clip.scale) - shot_scale_index(spec.scale))
    if diff == 0:
        return 1.0, True
    if diff == 1:
        return 0.5, True
    return -float(diff) * 0.5, True  # a big jump is a step back


def screen_direction_continuity(clip: ClipRecord, prev: ClipRecord | None) -> tuple[float, bool]:
    """Consecutive movement shots keep the same screen direction. Returns
    (bonus, applied) — applied only when both are movement shots with a
    direction and are adjacent."""
    if prev is None or prev.move is None or clip.move is None:
        return 0.0, False
    if not (prev.move in (CameraMove.TRACK, CameraMove.PAN, CameraMove.DRONE)
            and clip.move in (CameraMove.TRACK, CameraMove.PAN, CameraMove.DRONE)):
        return 0.0, False
    same = getattr(prev, "screen_direction", None) == getattr(clip, "screen_direction", None)
    return (1.0, True) if same else (-0.6, True)


def cut_on_action(_clip: ClipRecord, _spec: ShotSpec) -> tuple[float, bool]:
    """Cut lands where motion_energy is rising, never mid-peak (Plan D refines
    timing; here the soft signal is neutral). Returns (0, False)."""
    return 0.0, False


def hold_reaction(clip: ClipRecord, spec: ShotSpec) -> tuple[float, bool]:
    """After a PAYOFF beat, hold 0.5-1.0s before the next cut. Rewarded at the
    payoff shot itself. Returns (bonus, applied)."""
    if spec.function is ShotFunction.PAYOFF:
        return 1.0, True
    return 0.0, False


def no_repeat_subject(clip: ClipRecord, chosen: list[ClipRecord]) -> tuple[float, bool]:
    """Embedding/hash similarity to any already-selected clip > threshold ->
    reject (dedup across the whole video)."""
    if dedup_reject(clip, chosen):
        return -10.0, True
    return 0.0, False


def establish_first(spec: ShotSpec, shot_index: int) -> tuple[float, bool]:
    """Scene opens with ESTABLISH (LS/ELS) unless it's a continuation (index>0)
    or a cold-open. Rewarded only at the first shot of a scene."""
    if shot_index != 0:
        return 0.0, False
    if spec.function is ShotFunction.ESTABLISH and spec.scale in (ShotScale.LS, ShotScale.ELS):
        return 1.0, True
    return -0.5, True
