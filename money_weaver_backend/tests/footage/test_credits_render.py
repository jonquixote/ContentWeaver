from src.services.footage.credits import collect_render_credits, credits_manifest, credits_text
from src.services.cinema.clip import ClipRecord


def _clip(clip_id, req, text=None):
    return ClipRecord(clip_id=clip_id, provider="dareful", source_url="u",
                      duration_s=5.0, attribution_required=req, attribution_text=text)


def test_credits_block_mandatory_when_ccby_used():
    clips = [_clip("dareful:1", True, "Credit: Dareful"), _clip("pexels:2", False)]
    block = credits_text(clips)
    assert "Dareful" in block  # mandatory: CC-BY clip rendered -> credit present


def test_credits_block_empty_when_no_ccby():
    assert credits_text([_clip("pexels:2", False)]) == ""


def test_manifest_logged_per_render_shape():
    rows = credits_manifest([_clip("dareful:1", True, "Credit: Dareful")])
    assert rows[0]["clip_id"] == "dareful:1"


def test_collect_render_credits_from_video_data():
    # REAL wiring test (not inspection): synthetic render video_data
    # [(path, duration, metadata)] -> credit text in block. This pins the
    # attribution handoff through the download step, a known silent-drop seam
    # (metadata dicts losing attribution_required/text en route to the render).
    video_data = [
        ("/masters/archive_org/x/master.mp4", 8.0, {
            "source": "archive_org", "clip_id": "archive_org:x",
            "attribution_required": False, "attribution_text": None}),
        ("/masters/dareful/y/master.mp4", 6.0, {
            "source": "dareful", "clip_id": "dareful:y",
            "attribution_required": True, "attribution_text": "Credit: Dareful"}),
    ]
    block = collect_render_credits(video_data)
    assert "Dareful" in block  # CC-BY clip's credit survives the handoff


def test_collect_render_credits_empty_without_ccby():
    video_data = [("/masters/archive_org/x/master.mp4", 8.0, {
        "source": "archive_org", "clip_id": "archive_org:x",
        "attribution_required": False, "attribution_text": None})]
    assert collect_render_credits(video_data) == ""
