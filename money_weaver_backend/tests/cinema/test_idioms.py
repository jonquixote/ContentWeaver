from src.services.cinema.clip import ClipRecord
from src.services.cinema.idioms import (
    hold_reaction,
    no_repeat_subject,
    peaks_and_valleys,
    progressive_scale,
    screen_direction_continuity,
)
from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import CameraMove, MontageMode, ShotFunction, ShotScale


def _spec(scale=ShotScale.MS, move=CameraMove.STATIC, function=ShotFunction.CONTEXT, intensity=0.5, direction="neutral"):
    return ShotSpec(scene_number=1, shot_index=0, narrative_beats="b",
                    subject_concrete="s", scale=scale, move=move, function=function,
                    mood="dim", screen_direction=direction, intensity=intensity)


def _clip(clip_id="c", scale=ShotScale.MS, move=CameraMove.STATIC, direction="L2R", ah="a" * 16, dur=10.0):
    return ClipRecord(clip_id=clip_id, provider="pexels", source_url="u",
                      duration_s=dur, scale=scale, move=move, average_hash=ah)


def test_peaks_and_valleys_prefers_cu_on_high_intensity():
    # intensity high -> CU rewarded; LS punished
    hi = _spec(intensity=0.9)
    cu_bonus, _ = peaks_and_valleys(_clip(scale=ShotScale.CU), hi)
    ls_bonus, _ = peaks_and_valleys(_clip(scale=ShotScale.LS), hi)
    assert cu_bonus > ls_bonus


def test_peaks_and_valleys_prefers_ls_on_low_intensity():
    lo = _spec(intensity=0.1)
    ls_bonus, _ = peaks_and_valleys(_clip(scale=ShotScale.LS), lo)
    cu_bonus, _ = peaks_and_valleys(_clip(scale=ShotScale.CU), lo)
    assert ls_bonus > cu_bonus


def test_progressive_scale_promotes_ls_then_ms_then_cu():
    # Progressive: prefer LS->MS->CU ordering within a scene (move toward CU).
    first = _spec(scale=ShotScale.LS)
    cu_bonus, _ = progressive_scale(_clip(scale=ShotScale.CU), first, MontageMode.OVERTONAL)
    # earlier shot LS -> a CU is a forward jump, penalized vs an MS (closer step)
    ms_bonus, _ = progressive_scale(_clip(scale=ShotScale.MS), _spec(scale=ShotScale.MS), MontageMode.OVERTONAL)
    assert ms_bonus > cu_bonus  # matching scale preferred over a jump


def test_progressive_scale_inverts_under_intellectual():
    # Intellectual rewards juxtaposition (scale contrast), not progression.
    s = _spec(scale=ShotScale.MS)
    cu_bonus, _ = progressive_scale(_clip(scale=ShotScale.CU), s, MontageMode.INTELLECTUAL)
    ms_bonus, _ = progressive_scale(_clip(scale=ShotScale.MS), s, MontageMode.INTELLECTUAL)
    assert cu_bonus > ms_bonus  # inverted


def test_screen_direction_continuity_rewards_same_direction():
    prev = _clip(move=CameraMove.TRACK, direction="L2R")
    cur = _clip(move=CameraMove.TRACK, direction="L2R")
    bonus, applied = screen_direction_continuity(cur, prev)
    assert applied is True
    assert bonus > 0


def test_no_repeat_subject_rejects_near_dup():
    # dedup: a clip with the same average_hash as a chosen clip -> rejected
    chosen = [_clip(ah="a" * 16)]
    candidate = ClipRecord(clip_id="dup", provider="pexels", source_url="u",
                           duration_s=10.0, average_hash="a" * 16)
    bonus, rejected = no_repeat_subject(candidate, chosen)
    assert rejected is True
    assert bonus < 0


def test_hold_reaction_adds_duration_after_payoff():
    # PAYOFF function -> hold (bonus) longer before next cut
    payoff = ShotSpec(scene_number=1, shot_index=0, narrative_beats="b",
                      subject_concrete="s", scale=ShotScale.CU, move=CameraMove.STATIC,
                      function=ShotFunction.PAYOFF, mood="dim")
    bonus, held = hold_reaction(_clip(), payoff)
    assert held is True
    assert bonus > 0
