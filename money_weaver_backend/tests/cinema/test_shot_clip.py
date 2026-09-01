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
