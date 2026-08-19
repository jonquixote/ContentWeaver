from src.services.script_parsing_service import script_parsing_service

SAMPLE = """**Title: "Ocean"**

SCENE 1: Opening
[ACTION: a drone shot over the ocean]
NARRATOR
[DIALOGUE: The ocean covers most of the earth.]

CUT TO:

SCENE 2: Depth
[CAMERA: slow push-in on a reef]
NARRATOR
[DIALOGUE: Life thrives below.]

FADE OUT.

END
"""


def test_parse_blocks():
    parsed = script_parsing_service.parse_script(SAMPLE)
    assert parsed["title"] == "Ocean"
    assert len(parsed["scenes"]) == 2
    blocks = parsed["scenes"][0]["blocks"]
    types = [b["type"] for b in blocks]
    assert "heading" in types and "action" in types and "dialogue" in types


def test_extract_voiceover_uses_dialogue():
    parsed = script_parsing_service.parse_script(SAMPLE)
    vo = script_parsing_service.extract_voiceover_text(parsed)
    assert "ocean covers most of the earth" in vo.lower()


def test_transition_and_camera_detected():
    parsed = script_parsing_service.parse_script(SAMPLE)
    all_types = [b["type"] for s in parsed["scenes"] for b in s["blocks"]]
    assert "camera" in all_types
