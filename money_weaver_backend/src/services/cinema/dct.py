"""Small 2D DCT (low-frequency) using only numpy/math — no scipy dependency.

Used by perceptual_hash_from_bytes to produce a stable phash. Only the
low-frequency corner of the DCT is needed, computed with the separable 1D
cosine basis, which is O(N^3) for N=32 — tiny and fine on CPU.
"""

from __future__ import annotations

import math

import numpy as np


def dct_2d_lowfreq(arr: np.ndarray) -> np.ndarray:
    n = arr.shape[0]
    # orthonormal 1D DCT basis
    basis = np.zeros((n, n), dtype=np.float64)
    for k in range(n):
        alpha = math.sqrt(1.0 / n) if k == 0 else math.sqrt(2.0 / n)
        for x in range(n):
            basis[k, x] = alpha * math.cos(math.pi * (2 * x + 1) * k / (2 * n))
    return basis @ arr @ basis.T
