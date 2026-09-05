from src.services.cinema.timing_service import pacing_curve
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
