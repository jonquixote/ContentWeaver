import os
import tempfile

from src.services.footage.importers import ManualImporter, ManualImportError


def _mk(tmp):
    p = os.path.join(tmp, "clip.mp4")
    open(p, "wb").write(b"\x00" * 10)
    return p


def test_manual_import_rejects_unknown_license():
    tmp = tempfile.mkdtemp()
    imp = ManualImporter()
    import pytest
    with pytest.raises(ManualImportError):
        imp.import_path(_mk(tmp), "mixkit", "FAKE-LICENSE")


def test_manual_import_creates_candidate_with_provenance():
    tmp = tempfile.mkdtemp()
    imp = ManualImporter()
    c = imp.import_path(_mk(tmp), "mixkit", "LicenseRef-Mixkit",
                        attribution_required=False, attribution_text=None)
    assert c.source == "mixkit"
    assert c.license_spdx == "LicenseRef-Mixkit"
    assert c.page_url  # provenance recorded
    assert c.extras.get("attribution_required") is False


def test_manual_import_requires_source_license():
    tmp = tempfile.mkdtemp()
    imp = ManualImporter()
    import pytest
    with pytest.raises(ManualImportError):
        imp.import_path(_mk(tmp), "mixkit", None)  # no license -> reject


def test_manual_import_accepts_url():
    imp = ManualImporter()
    c = imp.import_path("https://example.com/clip.mp4", "dareful", "CC-BY-4.0",
                        attribution_required=True, attribution_text="Credit: Dareful")
    assert c.license_spdx == "CC-BY-4.0"
    assert c.attribution_text == "Credit: Dareful"
    assert c.extras.get("attribution_required") is True
    assert c.source_id.startswith("dareful:sha1:")  # deterministic url id
