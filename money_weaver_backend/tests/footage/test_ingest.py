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
