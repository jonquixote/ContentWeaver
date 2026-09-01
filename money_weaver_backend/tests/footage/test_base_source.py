import pytest

from src.services.footage.sources.base import BaseFootageSource, CandidateVideo, SearchPage


def test_candidate_video_shape():
    c = CandidateVideo(
        source="archive_org", source_id="123", title="T", description="D",
        tags=["a"], subjects=["b"], creator=None, published_at=None,
        duration_s=5.0, width=1920, height=1080, download_url="http://x/a.mp4",
        page_url="http://x/p", license_spdx="CC0-1.0", license_raw="PD",
        attribution_text=None, extras={},
    )
    assert c.source == "archive_org"
    assert c.license_spdx == "CC0-1.0"


def test_abstract_source_not_instantiable():
    with pytest.raises(TypeError):
        BaseFootageSource()


def test_subclass_must_implement_search():
    class Bad(BaseFootageSource):
        name = "bad"
        CREDIT_ATTRIBUTION = False
        strengths: list[str] = []
    with pytest.raises(TypeError):
        Bad()
