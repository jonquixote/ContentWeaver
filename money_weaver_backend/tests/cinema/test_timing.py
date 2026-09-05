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
