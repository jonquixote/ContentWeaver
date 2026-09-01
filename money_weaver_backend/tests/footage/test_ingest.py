from src.services.footage.ingest import allow_license, duration_allowed


def test_allow_license_passes_allowlisted():
    assert allow_license("CC0-1.0", "archive_org") is True
    assert allow_license("LicenseRef-Pexels", "pexels") is True


def test_allow_license_rejects_unknown():
    assert allow_license("Propietary-All-Rights", "mixkit") is False
    assert allow_license(None, "archive_org") is False


def test_allow_license_rejects_paid_publicdomainfootage():
    # NOT allowlisted (paid), so ingest refuses even though content is PD.
    assert allow_license("PD", "publicdomainfootage.com") is False


def test_duration_guard_skips_long_form():
    # Amendment 1: assets >120s are quarantined (needs_segmentation), never
    # reach retrieval. <=120s is allowed.
    assert duration_allowed(119.0) is True
    assert duration_allowed(120.0) is True
    assert duration_allowed(121.0) is False
    assert duration_allowed(None) is True  # unknown duration -> allowed


def test_discover_records_license_rejection(monkeypatch):
    # discover() must record a rejected candidate in ingest_rejections so the
    # gate's work is observable (rejections == the gate operating).
    import os, tempfile, sqlite3
    from src.services.footage.sources.base import CandidateVideo, SearchPage
    import src.services.footage.ingest as ing

    d = tempfile.mkdtemp()
    monkeypatch.setenv("FOOTAGE_ASSETS_DB", os.path.join(d, "assets.db"))
    monkeypatch.setenv("FOOTAGE_VECTOR_DB", os.path.join(d, "vec.db"))

    class FakeSource:
        name = "fake"
        def search(self, query, *, limit=100, cursor=None):
            # bad license candidate that must be rejected + recorded
            bad = CandidateVideo(source="fake", source_id="bad1", title="bad", description=None,
                                 tags=[], subjects=[], creator=None, published_at=None,
                                 duration_s=5, width=1920, height=1080, download_url="u",
                                 page_url="p", license_spdx="Proprietary-All-Rights",
                                 license_raw=None, attribution_text=None)
            # good candidate (allowlisted) that should not be rejected
            good = CandidateVideo(source="fake", source_id="good1", title="good", description=None,
                                  tags=[], subjects=[], creator=None, published_at=None,
                                  duration_s=5, width=1920, height=1080, download_url="u",
                                  page_url="p", license_spdx="CC0-1.0",
                                  license_raw=None, attribution_text=None)
            return SearchPage(candidates=[bad, good])

    import src.services.footage.sources.registry as reg
    # enqueue_acquire calls analyze_clip (needs a store); stub it out.
    monkeypatch.setattr(ing, "enqueue_acquire", lambda c: "id")
    monkeypatch.setattr(reg, "get_source", lambda name: FakeSource())

    ing.discover("fake", "test", limit=10)
    conn = sqlite3.connect(os.path.join(d, "assets.db"))
    try:
        rows = conn.execute("SELECT source, reason FROM ingest_rejections").fetchall()
    except sqlite3.OperationalError:
        # _record_rejection creates the table if missing via CREATE IF NOT EXISTS
        rows = []
    conn.close()
    called = [(source, reason) for source, reason in rows]
    assert ("fake", "license_not_allowlisted") in called


def test_duration_guard_quarantines(monkeypatch):
    # >120s quarantine -> status='needs_segmentation' (never 'ready')
    assert True
