import pytest

from pydantic import ValidationError

from src.services.cinema.shot import ShotSpec
from src.services.cinema.types import CameraMove, ShotFunction, ShotScale


def test_shotspec_defaults():
    spec = ShotSpec(
        scene_number=1,
        shot_index=0,
        narrative_beats="jokes fly",
        subject_concrete="comedian on stage with mic",
        scale=ShotScale.MS,
        move=CameraMove.STATIC,
        function=ShotFunction.ESTABLISH,
        mood="dim",
    )
    assert spec.screen_direction == "neutral"
    assert spec.intensity == 0.5
    assert spec.target_duration_s == 2.5
    assert spec.avoid_clip_ids == []


def test_shotspec_valid_string_values_coerce_to_enum():
    # str-subclass enums accept-and-coerce valid values in pydantic 2 (no raise)
    spec = ShotSpec(
        scene_number=1,
        shot_index=0,
        narrative_beats="x",
        subject_concrete="y",
        scale="mcu",
        move="static",
        function="establish",
        mood="dim",
    )
    assert spec.scale == ShotScale.MCU
    assert spec.move == CameraMove.STATIC
    assert spec.function == ShotFunction.ESTABLISH


def test_shotspec_rejects_unknown_enum_value():
    with pytest.raises(ValidationError):
        ShotSpec(
            scene_number=1,
            shot_index=0,
            narrative_beats="x",
            subject_concrete="y",
            scale="nonexistent",
            move="static",
            function="establish",
            mood="dim",
        )


from src.services.cinema.clip import ClipRecord


def test_cliprecord_defaults_are_nullable():
    c = ClipRecord(
        clip_id="pexels:123",
        provider="pexels",
        source_url="https://example.com/a.mp4",
        duration_s=12.0,
    )
    assert c.embedding is None
    assert c.scale is None
    assert c.move is None
    assert c.average_hash is None
    assert c.used_in_video_ids == []


def test_cliprecord_rejects_bad_provider():
    with pytest.raises(ValidationError):
        ClipRecord(clip_id="x", provider="youtube", source_url="u", duration_s=1.0)


def test_cliprecord_accepts_typed_optional_fields():
    from src.services.cinema.types import CameraMove, ShotScale
    c = ClipRecord(
        clip_id="pixabay:7",
        provider="pixabay",
        source_url="u",
        duration_s=5.0,
        scale=ShotScale.CU,
        move=CameraMove.DOLLY_IN,
        embedding=[0.1, 0.2, 0.3],
        average_hash="a1b2c3",
    )
    assert c.scale == ShotScale.CU
    assert len(c.embedding) == 3
