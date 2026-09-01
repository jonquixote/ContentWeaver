from src.services.cinema.modes import ModeConfig, get_mode_config
from src.services.cinema.types import MontageMode


def test_default_mode_is_overtonal():
    cfg = get_mode_config(MontageMode.OVERTONAL)
    assert isinstance(cfg, ModeConfig)
    assert cfg.w1 > 0 and cfg.w2 > 0 and cfg.w3 > 0


def test_metric_mode_zeroes_rhythm_terms():
    cfg = get_mode_config(MontageMode.METRIC)
    assert cfg.w3 == 0  # no tonal/neighbor weight in pure metric
    assert cfg.rhythmic is False


def test_intellectual_mode_inverts_contrast():
    cfg = get_mode_config(MontageMode.INTELLECTUAL)
    assert cfg.w3 < 0  # deliberate contrast


def test_all_modes_have_config():
    for m in MontageMode:
        assert get_mode_config(m) is not None
