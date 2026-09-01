from __future__ import annotations

from dataclasses import dataclass, field

from src.services.cinema.clip import ClipRecord
from src.services.cinema.idioms import (
    establish_first,
    hold_reaction,
    no_repeat_subject,
    peaks_and_valleys,
    progressive_scale,
)
from src.services.cinema.modes import get_mode_config
from src.services.cinema.scorer import rank_candidates, score
from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import MontageMode

IDIOM_WEIGHTS = {
    "peaks_and_valleys": 1.0,
    "progressive_scale": 1.0,
    "hold_reaction": 0.5,
    "establish_first": 0.8,
}


@dataclass
class TimelineShot:
    clip_id: str
    in_point_s: float
    out_point_s: float
    transition: str = "cut"
    function: str = "context"


@dataclass
class TimelinePlan:
    shots: list[TimelineShot] = field(default_factory=list)
    mode: MontageMode = MontageMode.OVERTONAL

    @property
    def total_s(self) -> float:
        return sum(s.out_point_s - s.in_point_s for s in self.shots)


def _idiom_bonus(clip: ClipRecord, spec: ShotSpec, prev: ClipRecord | None,
                 chosen: list[ClipRecord], shot_index: int) -> float:
    total = 0.0
    pv, _ = peaks_and_valleys(clip, spec)
    total += IDIOM_WEIGHTS["peaks_and_valleys"] * pv
    ps, _ = progressive_scale(clip, spec, _current_mode())
    total += IDIOM_WEIGHTS["progressive_scale"] * ps
    hr, _ = hold_reaction(clip, spec)
    total += IDIOM_WEIGHTS["hold_reaction"] * hr
    ef, _ = establish_first(spec, shot_index)
    total += IDIOM_WEIGHTS["establish_first"] * ef
    nr, _ = no_repeat_subject(clip, chosen)
    total += nr  # strong negative → dedup veto
    return total


_MODE: MontageMode = MontageMode.OVERTONAL


def _current_mode() -> MontageMode:
    return _MODE


def plan(
    shot_specs: list[ShotSpec],
    candidates: list[ClipRecord],
    *,
    mode: MontageMode = MontageMode.OVERTONAL,
) -> TimelinePlan:
    """Build a timeline plan (clip_id, in/out, transition) per ShotSpec under a
    montage mode. Cross-scene dedup enforced; empty input -> empty plan."""
    global _MODE
    _MODE = mode
    result = TimelinePlan(mode=mode)
    chosen: list[ClipRecord] = []  # accumulated across the whole video (dedup)
    for spec in shot_specs:
        # scorer's rank_candidates handles per-shot ranking + hashed dedup;
        # feed the chosen-so-far so cross-scene dedup binds.
        ranked = rank_candidates(candidates, spec, mode=mode, prev=(chosen[-1] if chosen else None), chosen=chosen)
        # prefer the top-ranked; apply idiom bonus as a tiebreak/ordering nudge
        best = None
        best_score = float("-inf")
        for clip in ranked:
            base = score(clip, spec, mode=mode, prev=(chosen[-1] if chosen else None), chosen=chosen)
            bonus = _idiom_bonus(clip, spec, (chosen[-1] if chosen else None), chosen, spec.shot_index)
            s = base + bonus
            if s > best_score:
                best_score = s
                best = clip
        if best is None:
            # graceful: no eligible clip for this shot (dedup exhausted) — skip
            # rather than raise (a scene is never left empty by reusing a clip).
            continue
        chosen.append(best)
        duration = min(best.duration_s or 2.5, spec.target_duration_s or 2.5)
        result.shots.append(TimelineShot(
            clip_id=best.clip_id,
            in_point_s=0.0,
            out_point_s=round(duration, 3),
            transition="cut",
            function=spec.function.value,
        ))
    return result
