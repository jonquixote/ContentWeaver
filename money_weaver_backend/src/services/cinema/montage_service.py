from __future__ import annotations

from dataclasses import dataclass, field

from src.services.cinema.clip import ClipRecord
from src.services.cinema.idioms import (
    cut_on_action,
    establish_first,
    hold_reaction,
    no_repeat_subject,
    peaks_and_valleys,
    progressive_scale,
    screen_direction_continuity,
)
from src.services.cinema.scorer import rank_candidates, score
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
                 chosen: list[ClipRecord], shot_index: int,
                 mode: MontageMode) -> float:
    total = 0.0
    pv, _ = peaks_and_valleys(clip, spec)
    total += IDIOM_WEIGHTS["peaks_and_valleys"] * pv
    # progressive_scale() inverts internally under Intellectual (contrast
    # preferred), so it is always called with the mode — no gate needed.
    ps, _ = progressive_scale(clip, spec, mode)
    total += IDIOM_WEIGHTS["progressive_scale"] * ps
    hr, _ = hold_reaction(clip, spec)
    total += IDIOM_WEIGHTS["hold_reaction"] * hr
    ef, _ = establish_first(spec, shot_index)
    total += IDIOM_WEIGHTS["establish_first"] * ef
    sd, _ = screen_direction_continuity(clip, prev)
    total += sd
    # cut_on_action is intentionally neutral (returns 0, False) until Plan D
    # timing data exists; called for completeness so the wiring is visible.
    coa, _ = cut_on_action(clip, spec)
    total += coa
    nr, _ = no_repeat_subject(clip, chosen)
    total += nr  # strong negative → dedup veto
    return total


def plan(
    shot_specs: list[ShotSpec],
    candidates: list[ClipRecord],
    *,
    mode: MontageMode = MontageMode.OVERTONAL,
) -> TimelinePlan:
    """Build a timeline plan (clip_id, in/out, transition) per ShotSpec under a
    montage mode. Cross-scene dedup enforced; empty input -> empty plan."""
    result = TimelinePlan(mode=mode)
    chosen: list[ClipRecord] = []  # accumulated across the whole video (dedup)
    for spec in shot_specs:
        # scorer's rank_candidates handles per-shot ranking + hashed dedup;
        # feed the chosen-so-far so cross-scene dedup binds.
        ranked = rank_candidates(candidates, spec, mode=mode, prev=(chosen[-1] if chosen else None), chosen=chosen)
        if not ranked:
            # Pool exhausted: every candidate vetoed by the hash dedup. Retry
            # WITHOUT the veto so the shot is never silently dropped (reuse is
            # preferable to a gap; the reuse is visible in the plan).
            print(f"montage: pool exhausted for shot {spec.shot_index}, retrying without hash veto")
            ranked = rank_candidates(candidates, spec, mode=mode, prev=(chosen[-1] if chosen else None), chosen=chosen, relax_dedup=True)
        # Rank-then-rescore is intentional: rank_candidates() orders by the
        # scorer alone (fast filter + dedup), then this loop re-scores the
        # survivors adding idiom bonuses that need shot context (progression,
        # direction, payoff holds) the scorer cannot see.
        best = None
        best_score = float("-inf")
        for clip in ranked:
            base = score(clip, spec, mode=mode, prev=(chosen[-1] if chosen else None), chosen=chosen)
            bonus = _idiom_bonus(clip, spec, (chosen[-1] if chosen else None), chosen, spec.shot_index, mode)
            s = base + bonus
            if s > best_score:
                best_score = s
                best = clip
        if best is None:
            # No candidates at all (empty pool even relaxed) — skip rather than
            # raise. The shot-count assertion in tests pins this stays rare.
            print(f"montage: no candidates for shot {spec.shot_index}, skipping")
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
