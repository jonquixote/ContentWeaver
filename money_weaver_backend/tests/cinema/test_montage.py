from src.services.cinema.clip import ClipRecord
from src.services.cinema.montage_service import TimelinePlan, TimelineShot, plan
from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import CameraMove, MontageMode, ShotFunction, ShotScale


def _spec(scale=ShotScale.MS, move=CameraMove.STATIC, function=ShotFunction.CONTEXT, scene=1, idx=0, intensity=0.5):
    return ShotSpec(scene_number=scene, shot_index=idx, narrative_beats="b",
                    subject_concrete="s", scale=scale, move=move, function=function,
                    mood="dim", screen_direction="neutral", intensity=intensity,
                    target_duration_s=2.5)


def _clip(clip_id, scale=ShotScale.MS, move=CameraMove.STATIC, dur=8.0, ah=None):
    # average_hash must be hex (hamming_distance int()s it). Derive a stable hex
    # from the clip_id so distinct clips get distinct hashes.
    import hashlib
    h = ah or hashlib.sha1(clip_id.encode()).hexdigest()[:16]
    return ClipRecord(clip_id=clip_id, provider="pexels", source_url="u",
                      duration_s=dur, scale=scale, move=move, average_hash=h)


def test_plan_returns_empty_for_empty_input():
    result = plan([], [])
    assert isinstance(result, TimelinePlan)
    assert result.shots == []


def test_plan_produces_one_shot_per_spec():
    specs = [_spec(idx=0), _spec(idx=1), _spec(idx=2)]
    clips = [_clip(str(i)) for i in range(5)]
    result = plan(specs, clips)
    assert len(result.shots) == 3
    for shot in result.shots:
        assert isinstance(shot, TimelineShot)
        assert shot.clip_id
        assert shot.in_point_s < shot.out_point_s


def test_plan_cross_scene_dedup_no_clip_reused():
    # cross-scene dedup: the same clip must not be selected for two shots.
    # Shot-count assertion pins the behavior: with only ONE distinct clip
    # (both near-dups of each other), the second shot must relax the veto and
    # STILL produce a shot (pool-exhaustion retry) rather than silently drop.
    specs = [_spec(idx=0), _spec(idx=1)]
    clips = [_clip("a", ah="1" * 16), _clip("b", ah="1" * 16)]  # near-dup (same hash)
    result = plan(specs, clips)
    assert len(result.shots) == 2  # both shots present — none silently dropped
    # Note: with the pool exhausted, the relaxed retry may reuse a clip; the
    # no-reuse property holds only when distinct candidates exist (see the
    # never-duplicates test below).


def test_plan_pool_exhaustion_retries_without_veto(capsys):
    # Pool exhaustion: all candidates vetoed -> retry without hash veto + log.
    specs = [_spec(idx=0), _spec(idx=1), _spec(idx=2)]
    clips = [_clip("only", ah="2" * 16)]
    result = plan(specs, clips)
    out = capsys.readouterr().out
    assert "montage: pool exhausted for shot" in out
    assert len(result.shots) == 3  # every shot filled via the relaxed retry


def test_plan_progressive_scale_orders_ls_to_cu(monkeypatch):
    # capture chosen in order to assert LS->MS->CU progression across the plan
    specs = [
        _spec(scale=ShotScale.LS, idx=0, scene=1),
        _spec(scale=ShotScale.MS, idx=1, scene=1),
        _spec(scale=ShotScale.CU, idx=2, scene=1),
    ]
    clips = [
        _clip("ls", scale=ShotScale.LS),
        _clip("ms", scale=ShotScale.MS),
        _clip("cu", scale=ShotScale.CU),
    ]
    result = plan(specs, clips)
    assert [s.clip_id for s in result.shots] == ["ls", "ms", "cu"]


def test_plan_inverts_under_intellectual(monkeypatch):
    # Intellectual: contrast preferred (CU chosen for an MS target, not an MS clip)
    specs = [_spec(scale=ShotScale.MS, idx=0, scene=1)]
    clips = [
        _clip("ms", scale=ShotScale.MS),
        _clip("cu", scale=ShotScale.CU),
    ]
    result = plan(specs, clips, mode=MontageMode.INTELLECTUAL)
    assert result.shots[0].clip_id == "cu"


def test_plan_never_produces_duplicate_ids_across_scenes():
    specs = [_spec(idx=i, scene=i + 1) for i in range(4)]
    clips = [_clip(str(i), ah=hex(i + 1)[2:].zfill(16)) for i in range(8)]
    result = plan(specs, clips)
    ids = [s.clip_id for s in result.shots]
    assert len(set(ids)) == len(ids)
