from src.services.cinema.hash_util import (
    average_hash_from_bytes,
    hamming_distance,
    perceptual_hash_from_bytes,
)

# 1x1 black PNG via Pillow (deterministic, no network)
from PIL import Image
import io


def _png_bytes(color=(0, 0, 0), size=(8, 8)):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _gradient_png(top=(0, 0, 0), bottom=(255, 255, 255), size=(16, 16)):
    """Non-uniform image so an average hash discriminates it (avg-hash ignores
    flat-color images — they all hash to 0x0000...)."""
    import numpy as np
    arr = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        arr[y, :, :] = (
            int(top[0] + (bottom[0] - top[0]) * t),
            int(top[1] + (bottom[1] - top[1]) * t),
            int(top[2] + (bottom[2] - top[2]) * t),
        )
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_average_hash_is_stable_and_hex():
    h = average_hash_from_bytes(_png_bytes())
    assert isinstance(h, str)
    assert len(h) == 16  # 64-bit hash as 16 hex chars


def test_same_image_same_hash():
    assert average_hash_from_bytes(_png_bytes((10, 20, 30))) == average_hash_from_bytes(
        _png_bytes((10, 20, 30))
    )


def test_different_images_different_hash():
    a = average_hash_from_bytes(_gradient_png(top=(0, 0, 0), bottom=(255, 255, 255)))
    b = average_hash_from_bytes(_gradient_png(top=(255, 255, 255), bottom=(0, 0, 0)))
    assert a != b


def test_perceptual_hash_available():
    h = perceptual_hash_from_bytes(_png_bytes())
    assert len(h) == 16


def test_hamming_distance_identical_is_zero():
    h = average_hash_from_bytes(_png_bytes((1, 2, 3)))
    assert hamming_distance(h, h) == 0


def test_hamming_distance_limits():
    # 0xFFFFFFFFFFFFFFFF vs 0x0000000000000000 -> 64 different bits
    assert hamming_distance("ffffffffffffffff", "0000000000000000") == 64


def test_dedup_threshold_rule_is_six():
    # two all-black against a flipped near-identical (bit diff small) must be <= 6
    a = average_hash_from_bytes(_png_bytes((4, 8, 12)))
    b = average_hash_from_bytes(_png_bytes((5, 9, 13)))
    assert hamming_distance(a, b) <= 6
