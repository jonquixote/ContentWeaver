from src.services.cinema.clip import ClipRecord
from src.services.cinema.scorer import (
    dedup_reject,
    neighbor_term,
    quality,
    rank_candidates,
    typed_match,
)
from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import CameraMove, MontageMode, ShotFunction, ShotScale


def _clip(clip_id, provider="pexels", duration=10, scale=None, move=None, ah=None):
    return ClipRecord(
        clip_id=clip_id, provider=provider, source_url=f"https://u/{clip_id}",
        duration_s=duration, width=1920, height=1080, scale=scale, move=move,
        average_hash=ah,
    )


def _spec(scale=ShotScale.MS, move=CameraMove.STATIC, function=ShotFunction.CONTEXT):
    return ShotSpec(
        scene_number=1, shot_index=0, narrative_beats="jokes",
        subject_concrete="comedian with mic on stage", scale=scale,
        move=move, function=function, mood="dim",
    )


def test_typed_match_scores_scale_match():
    s = _spec()
    assert typed_match(_clip("a", scale=ShotScale.MS), s) > typed_match(
        _clip("b", scale=ShotScale.ELS), s
    )


def test_none_typed_fields_are_neutral_not_mismatch():
    # clip with scale=None scores 0 contribution, not negative
    clip_no_scale = _clip("c", scale=None)
    assert typed_match(clip_no_scale, _spec()) == 0.0


def test_quality_rewards_good_resolution():
    hi = _clip("hi", duration=12)
    assert quality(hi) > 0


def test_dedup_reject_by_hash_within_duration():
    # same hash AND duration within +-1s -> reject
    a = _clip("a", duration=10, ah="0000000000000000")
    b = _clip("b", duration=10.5, ah="0000000000000001")  # 1 bit diff, dur close
    assert dedup_reject(a, [b]) is True


def test_dedup_does_not_reject_when_duration_far():
    # same hash but duration differs by >1s -> guard against flat-thumbnail
    # aHash collisions where two clips share an all-zero hash but differ in length
    a = _clip("a", duration=10, ah="0000000000000000")
    b = _clip("b", duration=20, ah="0000000000000000")  # same hash, far duration
    assert dedup_reject(a, [b]) is False


def test_dedup_does_not_reject_when_hash_far():
    c = _clip("c", duration=10, ah="ffffffffffffffff")
    b = _clip("b", duration=10, ah="0000000000000000")
    assert dedup_reject(c, [b]) is False  # far apart -> not rejected


def test_rank_candidates_orders_and_dedups():
    clips = [
        _clip("dup1", duration=10, scale=ShotScale.MS, ah="1111111111111111"),
        _clip("dup2", duration=10.2, scale=ShotScale.MS, ah="1111111111111111"),  # near-dup
        _clip("good", duration=10, scale=ShotScale.MS, ah="aaaaaaaaaaaaaaaa"),
        _clip("bad", duration=10, scale=ShotScale.ELS, ah="bbbbbbbbbbbbbbbb"),
    ]
    ranked = rank_candidates(clips, _spec())
    ids = [c.clip_id for c in ranked]
    assert "good" in ids
    # only one of dup1/dup2 survives (near-dup deduped)
    assert ("dup1" in ids) != ("dup2" in ids)


def test_neighbor_term_tonal_vs_intellectual():
    prev = _clip("p", scale=ShotScale.CU, move=CameraMove.DOLLY_IN)
    cur = _clip("c", scale=ShotScale.CU, move=CameraMove.DOLLY_IN)
    # tonal rewards similarity
    assert neighbor_term(cur, prev, MontageMode.TONAL) > 0
    # intellectual penalizes sameness
    assert neighbor_term(cur, prev, MontageMode.INTELLECTUAL) < 0


def test_rank_candidates_respects_cross_shot_chosen():
    # clip picked for an EARLIER shot (passed as `chosen`) must exclude its
    # near-dup from this shot's ranking (cross-shot dedup).
    earlier = _clip("earlier", duration=10, scale=ShotScale.MS, ah="1111111111111111")
    later_candidates = [
        _clip("neardup", duration=10.2, scale=ShotScale.MS, ah="1111111111111110"),  # near-dup of earlier
        _clip("fresh", duration=11, scale=ShotScale.MS, ah="aaaaaaaaaaaaaaaa"),
        _clip("fresh2", duration=12, scale=ShotScale.MS, ah="bbbbbbbbbbbbbbbb"),
    ]
    ranked = rank_candidates(later_candidates, _spec(), chosen=[earlier])
    ids = [c.clip_id for c in ranked]
    assert "neardup" not in ids  # excluded because it duplicates `earlier`
    assert "fresh" in ids
