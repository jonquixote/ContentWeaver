"""Average / perceptual hashing of provider preview thumbnails (Pillow/numpy).

This is the PINNED dedup mechanism for the cinema engine. Dedup is decided on
image content — never on URL or provider ID, because the same clip can appear
under two URLs or two IDs and must be caught.
"""

from __future__ import annotations

import hashlib
import io

import numpy as np
from PIL import Image


def _open_image(image_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def average_hash_from_bytes(image_bytes: bytes, hash_size: int = 8) -> str:
    """Return hex digest of an 8x8 average hash (64 bits -> 16 hex chars)."""
    img = _open_image(image_bytes).resize((hash_size, hash_size), Image.LANCZOS)
    arr = np.asarray(img, dtype=np.float32).mean(axis=2)  # grayscale 8x8
    mean = arr.mean()
    bits = (arr > mean).flatten().astype(np.uint8)
    return _bits_to_hex(bits)


def perceptual_hash_from_bytes(image_bytes: bytes, hash_size: int = 8) -> str:
    """Return hex digest of a DCT-based perceptual hash (phash)."""
    img = _open_image(image_bytes)
    img = img.resize((32, 32), Image.LANCZOS).convert("L")
    arr = np.asarray(img, dtype=np.float32)
    # low-frequency DCT coefficients via numpy (no scipy)
    from src.services.cinema.dct import dct_2d_lowfreq

    coeffs = dct_2d_lowfreq(arr)
    # take top-left hash_size x hash_size low-frequency block
    block = coeffs[:hash_size, :hash_size]
    med = np.median(block[1:, :])  # exclude DC for stabler sign
    bits = (block > med).flatten().astype(np.uint8)
    return _bits_to_hex(bits)


def hamming_distance(a_hex: str, b_hex: str) -> int:
    """Hamming distance between two hex-encoded 64-bit hashes."""
    a = int(a_hex, 16)
    b = int(b_hex, 16)
    return bin(a ^ b).count("1")


def _bits_to_hex(bits: np.ndarray) -> str:
    # bits is 0/1 uint8 array of length 64
    chunk = int("".join(str(int(b)) for b in bits), 2)
    return f"{chunk:016x}"
