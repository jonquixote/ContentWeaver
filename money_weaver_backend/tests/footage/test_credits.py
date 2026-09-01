from src.services.footage.credits import credits_manifest, credits_text
from src.services.cinema.clip import ClipRecord


def _nd_clip():
    # ND source (no credit required) — attribution_required default False
    return ClipRecord(clip_id="mixkit:1", provider="mixkit", source_url="u", duration_s=5.0)


def _credit_clip():
    return ClipRecord(
        clip_id="dareful:1", provider="dareful", source_url="u", duration_s=5.0,
        attribution_required=True, attribution_text="Credit: Dareful",
    )


def test_credits_manifest_omits_no_credit_clips():
    assert credits_manifest([_nd_clip()]) == []


def test_credits_manifest_lists_attribution_required():
    manifest = credits_manifest([_credit_clip()])
    assert manifest[0]["clip_id"] == "dareful:1"
    assert manifest[0]["attribution_text"] == "Credit: Dareful"


def test_credits_text_builds_block_when_needed():
    text = credits_text([_credit_clip()])
    assert "Dareful" in text
    assert credits_text([_nd_clip()]) == ""


def test_credits_manifest_mixed():
    manifest = credits_manifest([_nd_clip(), _credit_clip()])
    assert [m["clip_id"] for m in manifest] == ["dareful:1"]