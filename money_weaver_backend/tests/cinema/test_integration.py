from src.services.cinema.types import CameraMove, ShotScale
from src.services.script_parsing_service import ScriptParsingService


def _minimal_scene():
    return {
        "scene_number": 3,
        "description": "Meet the Heckler",
        "start_time": 0,
        "end_time": 0,
        "duration": 0,
        "blocks": [
            {"type": "camera", "text": "close-up, slow dolly in"},
            {"type": "action", "text": "a nervous comedian adjusts the mic"},
            {"type": "dialogue", "text": '"this is not my future"'},
        ],
    }


def test_parsed_blocks_to_shotspecs_keeps_camera_typed():
    svc = ScriptParsingService()
    specs = svc.parsed_blocks_to_shotspecs(_minimal_scene())
    assert specs
    spec = specs[0]
    assert spec.scene_number == 3
    assert spec.scale == ShotScale.CU  # "close-up" -> CU
    assert spec.move == CameraMove.DOLLY_IN  # "dolly in" -> dolly_in
    assert spec.subject_concrete  # concrete subject from action block


def test_parse_screenplay_then_shotspecs():
    svc = ScriptParsingService()
    script = (
        "**Scene 1: The Comedy Club (0s-5s)**\n"
        "[CAMERA: medium shot, static]\n"
        "[ACTION: a dimly lit comedy club with a nervous comedian]\n"
        'Voiceover: "In a bustling comedy club, a hopeful comedian prepares."\n'
        "END"
    )
    scenes = svc.parse_screenplay(script)
    target = scenes[0] if scenes else {}
    specs = svc.parsed_blocks_to_shotspecs(target)
    assert specs
    assert all(s.subject_concrete for s in specs)
    assert specs[0].move == CameraMove.STATIC
