from src.services.cinema.types import CameraMove, MontageMode, ShotFunction, ShotScale


def test_shot_scale_members():
    assert ShotScale.ECU.value == "ecu"
    assert ShotScale.ELS.value == "els"
    assert ShotScale.ABSTRACT.value == "abstract"


def test_camera_move_members():
    assert CameraMove.DOLLY_IN.value == "dolly_in"
    assert CameraMove.STATIC.value == "static"
    assert CameraMove.ZOOM.value == "zoom"


def test_shot_function_members():
    assert ShotFunction.ESTABLISH.value == "establish"
    assert ShotFunction.PAYOFF.value == "payoff"


def test_montage_mode_members():
    assert MontageMode.OVERTONAL.value == "overtonal"
    assert MontageMode.INTELLECTUAL.value == "intellectual"


def test_enum_iteration_is_stringly_typed():
    assert all(isinstance(v.value, str) for v in ShotScale)
