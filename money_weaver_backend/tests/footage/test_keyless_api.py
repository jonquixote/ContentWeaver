import os

import pytest
import vcr

from src.services.footage.sources.keyless import (
    NasaImagesSource,
    PexelsSource,
    PixabaySource,
)

CASSETTE_DIR = os.path.join(os.path.dirname(__file__), "cassettes")


@pytest.fixture
def vcr_record(monkeypatch):
    # Load .env so PEXELS_API_KEY/PIXABAY_API_KEY are present during cassette
    # recording (the adapters short-circuit to empty results on missing keys).
    from dotenv import load_dotenv
    load_dotenv()
    return vcr.VCR(
        cassette_library_dir=CASSETTE_DIR,
        record_mode="once",
        filter_headers=["authorization", "key"],
        match_on=["method", "path", "query"],
    )


def test_pexels_search_returns_candidates_with_duration(vcr_record):
    with vcr_record.use_cassette("pexels_search.yaml"):
        src = PexelsSource()
        page = src.search("aerial coastline", limit=3)
    assert page.candidates
    c = page.candidates[0]
    assert c.source == "pexels"
    assert c.duration_s is not None  # durations present for the duration guard
    assert c.width and c.height
    assert c.license_spdx == "LicenseRef-Pexels"
    assert c.source_id


def test_pixabay_search_returns_candidates_with_duration(vcr_record):
    with vcr_record.use_cassette("pixabay_search.yaml"):
        src = PixabaySource()
        page = src.search("aerial", limit=3)
    assert page.candidates
    c = page.candidates[0]
    assert c.source == "pixabay"
    assert c.duration_s is not None
    assert c.license_spdx == "LicenseRef-Pixabay"


def test_nasa_search_returns_candidates_pd(vcr_record):
    with vcr_record.use_cassette("nasa_search.yaml"):
        src = NasaImagesSource()
        page = src.search("earth orbit", limit=3)
    assert page.candidates
    c = page.candidates[0]
    assert c.source == "nasa_images"
    assert c.license_spdx == "nasa-media-guidelines"
    assert c.page_url.startswith("https://images.nasa.gov/details/")


def test_nasa_search_is_allowlisted():
    # nasa-media-guidelines must be allowlisted (it maps to a license the gate accepts)
    from src.services.footage.ingest import allow_license
    assert allow_license("nasa-media-guidelines", "nasa_images") is True
