import numpy as np
import pytest

from src.services.cinema.dct import dct_2d_lowfreq


def test_dct_shape_and_value():
    arr = np.random.RandomState(0).rand(32, 32)
    out = dct_2d_lowfreq(arr)
    assert out.shape == (32, 32)
    # DC coefficient should be the largest-magnitude (brightness) term
    assert abs(out[0, 0]) == pytest.approx(abs(out).max(), rel=0.6)
