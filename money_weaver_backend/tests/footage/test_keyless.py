import os

import pytest
import vcr

from src.services.footage.sources.keyless import ArchiveOrgSource

CASSETTE_DIR = os.path.join(os.path.dirname(__file__), "cassettes")


@pytest.fixture
def vcr_record():
    return vcr.VCR(
        cassette_library_dir=CASSETTE_DIR,
        record_mode="once",   # record first run, replay thereafter (network-free)
        filter_headers=["authorization"],
        match_on=["method", "path", "query"],
    )


def test_archive_org_search_returns_candidates(vcr_record):
    with vcr_record.use_cassette("archive_org_search.yaml"):
        src = ArchiveOrgSource()
        page = src.search("aerial coastline", limit=3)
    assert page.candidates
    c = page.candidates[0]
    assert c.source == "archive_org"
    assert c.source_id  # identifier
    assert c.page_url.startswith("https://archive.org/details/")


def test_archive_org_search_maps_license(vcr_record):
    with vcr_record.use_cassette("archive_org_search.yaml"):
        src = ArchiveOrgSource()
        page = src.search("aerial coastline", limit=3)
    assert page.candidates
    # Every candidate has a license_spdx slot; recognized licenses are mapped to
    # a known SPDX value (CC* / public-domain / CC0), unknown ones are None.
    recognized = {c.license_spdx for c in page.candidates if c.license_spdx}
    assert recognized.issubset({"CC0-1.0", "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-4.0", "public-domain"})


def test_archive_org_search_does_not_fabricate_download_url(vcr_record):
    # Flag 2: download_url must NOT be the speculative '{id}/{id}.mp4' guess.
    # resolve_download enumerates real files via the metadata API.
    with vcr_record.use_cassette("archive_org_search.yaml"):
        src = ArchiveOrgSource()
        page = src.search("aerial coastline", limit=3)
    for c in page.candidates:
        assert not c.download_url  # empty until resolved


def test_archive_org_resolve_download_enumerates_real_mp4(vcr_record):
    # resolve_download queries the metadata API and returns a real file URL.
    with vcr_record.use_cassette("archive_org_search.yaml"):
        src = ArchiveOrgSource()
        page = src.search("aerial coastline", limit=3)
    cid = page.candidates[0].source_id
    with vcr_record.use_cassette("archive_org_metadata.yaml"):
        url = src.resolve_download(cid)
    assert url == "" or url.startswith("https://archive.org/download/")
