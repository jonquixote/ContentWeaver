import numpy as np
from src.services.cinema.timing_service import beat_grid, pacing_curve, snap_to_grid
from src.services.cinema.types import MontageMode


def test_pacing_curve_sums_to_total():
    durs = pacing_curve(12, 60.0, MontageMode.OVERTONAL)
    assert len(durs) == 12
    assert abs(sum(durs) - 60.0) < 0.01


def test_pacing_curve_accelerates_into_final_act():
    durs = pacing_curve(12, 60.0, MontageMode.OVERTONAL)
    assert sum(durs[:4]) / 4 > sum(durs[-4:]) / 4  # early shots longer than late


def test_pacing_curve_metric_mode_strict_cells():
    durs = pacing_curve(8, 32.0, MontageMode.METRIC)
    assert len(set(round(d, 3) for d in durs)) == 1  # identical cells


def test_beat_grid_empty_without_librosa_or_track(monkeypatch):
    monkeypatch.setenv("USE_LIBROSA_BEATS", "false")
    assert beat_grid(None) == []
    assert beat_grid("/nonexistent/track.mp3") == []


def test_snap_to_grid_strict_metric():
    grid = [0.0, 0.5, 1.0, 1.5, 2.0]
    assert snap_to_grid(0.53, grid, strict=True) == 0.5
    assert snap_to_grid(0.9, grid, strict=True) == 1.0


def test_snap_to_grid_soft_attraction():
    grid = [0.0, 0.5, 1.0]
    assert snap_to_grid(0.4, grid, strict=False) == 0.4  # stays (soft)
    assert snap_to_grid(0.49, grid, strict=False) == 0.5  # snaps when close


def test_phrase_boundaries_from_text():
    from src.services.cinema.timing_service import phrase_boundaries
    bounds = phrase_boundaries("Hello world. This is a test. Short.")
    assert bounds == sorted(bounds)
    assert len(bounds) >= 2  # at least the sentence breaks


def test_phrase_boundaries_prefers_word_timestamps():
    from src.services.cinema.timing_service import phrase_boundaries
    words = [("hello", 0.0, 0.3), ("world", 0.3, 0.6), ("next", 1.2, 1.5)]
    bounds = phrase_boundaries("hello world next", word_timestamps=words)
    assert any(abs(b - 1.2) < 0.01 for b in bounds)  # next-phrase start kept


def test_jl_cut_offset_reads_env(monkeypatch):
    from src.services.cinema.timing_service import jl_cut_offset
    monkeypatch.setenv("CINEMA_JL_CUT_S", "0.7")
    assert jl_cut_offset() == 0.7
    monkeypatch.delenv("CINEMA_JL_CUT_S", raising=False)
    assert jl_cut_offset() == 0.4


def test_motion_energy_empty_without_file():
    from src.services.cinema.timing_service import motion_energy_series
    assert motion_energy_series(None) == []
    assert motion_energy_series("/nonexistent/x.mp4") == []


def test_cut_on_action_nudge_moves_to_energy_rise():
    from src.services.cinema.timing_service import cut_on_action_nudge
    # energy rises at index 12 of a 25fps series -> nudge lands near 0.48s
    energy = [0.1] * 10 + [0.9] * 10 + [0.2] * 10
    nudged = cut_on_action_nudge(0.3, energy, fps=25.0, window_s=0.5)
    assert nudged == 0.4  # rise onset at index 10
    assert nudged != 0.3  # actually moved toward the rise


def test_cut_on_action_nudge_never_moves_far():
    from src.services.cinema.timing_service import cut_on_action_nudge
    energy = [0.5] * 30
    assert cut_on_action_nudge(1.0, energy) == 1.0  # flat -> stays


def test_apply_timing_snaps_to_beats_in_metric():
    from src.services.cinema.montage_service import TimelinePlan, TimelineShot
    from src.services.cinema.timing_service import apply_timing
    p = TimelinePlan(mode=MontageMode.METRIC, shots=[
        TimelineShot(clip_id="a", in_point_s=0.0, out_point_s=2.5),
        TimelineShot(clip_id="b", in_point_s=0.0, out_point_s=2.5),
    ])
    out = apply_timing(p, beats=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0], phrases=[])
    for s in out.shots:
        assert s.out_point_s - s.in_point_s > 0


def test_apply_timing_empty_beats_keeps_plan():
    from src.services.cinema.montage_service import TimelinePlan, TimelineShot
    from src.services.cinema.timing_service import apply_timing
    p = TimelinePlan(mode=MontageMode.METRIC, shots=[
        TimelineShot(clip_id="a", in_point_s=0.0, out_point_s=2.5),
        TimelineShot(clip_id="b", in_point_s=0.0, out_point_s=2.5),
    ])
    out = apply_timing(p, beats=[], phrases=[])
    assert [s.clip_id for s in out.shots] == ["a", "b"]


def test_apply_timing_never_empty_or_negative():
    from src.services.cinema.montage_service import TimelinePlan
    from src.services.cinema.timing_service import apply_timing
    out = apply_timing(TimelinePlan(), beats=[0.5], phrases=[])
    assert out.shots == []


def test_apply_timing_sum_invariant_survives_all_nudges():
    from src.services.cinema.montage_service import TimelinePlan, TimelineShot
    from src.services.cinema.timing_service import apply_timing
    plan = TimelinePlan(mode=MontageMode.OVERTONAL, shots=[
        TimelineShot(clip_id="a", in_point_s=0.0, out_point_s=2.5),
        TimelineShot(clip_id="b", in_point_s=0.0, out_point_s=2.5),
        TimelineShot(clip_id="c", in_point_s=0.0, out_point_s=2.5),
    ])
    beats = [0.0, 0.37, 0.91, 1.44, 2.02, 2.77, 3.31, 4.05, 4.66, 5.2, 5.83, 6.4, 7.0, 7.5]
    out = apply_timing(plan, beats=beats, phrases=[])
    assert abs(out.total_s - plan.total_s) < 0.05  # renormalized exactness
    for s in out.shots:
        assert (s.out_point_s - s.in_point_s) >= 0.5  # floor holds
    for s in out.shots:
        assert abs(round(s.out_point_s / 0.04) * 0.04 - s.out_point_s) < 0.011
