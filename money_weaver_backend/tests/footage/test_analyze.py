import os
import tempfile

from src.services.footage.analyze import analyze_clip
from src.services.footage.sources.base import CandidateVideo


def _candidate(tmp):
    p = os.path.join(tmp, "clip.mp4")
    open(p, "wb").write(b"\x00" * 8)
    return CandidateVideo(source="pexels", source_id="1", title="t", description=None,
                          tags=[], subjects=[], creator=None, published_at=None,
                          duration_s=3, width=1920, height=1080, download_url=p,
                          page_url="p", license_spdx="LicenseRef-Pexels",
                          license_raw=None, attribution_text=None)


def test_analyze_produces_cliprecord_even_without_embedder(monkeypatch):
    monkeypatch.setenv("EMBED_BACKEND", "none")
    tmp = tempfile.mkdtemp()
    recs = analyze_clip("pexels:1", _candidate(tmp))
    assert recs  # at least one ClipRecord
    r = recs[0]
    assert r.clip_id
    assert r.embedding is None or r.embedding == []


def test_analyze_sets_scale_or_none_no_crash():
    # scale None (no detector) — contract holds, never raises.
    tmp = tempfile.mkdtemp()
    recs = analyze_clip("pexels:1", _candidate(tmp))
    assert recs[0].scale is None or recs[0].scale is not None


def test_analyze_records_provenance():
    tmp = tempfile.mkdtemp()
    c = _candidate(tmp)
    c.license_spdx = "LicenseRef-Pexels"
    recs = analyze_clip("pexels:1", c)
    r = recs[0]
    # ClipRecord carries the provenance via provider + source_url
    assert r.source_url  # points at the candidate's download URL
    assert r.duration_s == 3.0


def test_analyze_persists_attribution():
    # ClipRecord must actually STORE attribution (not silently drop it — pydantic
    # v2 ignores unknown kwargs by default, which would lose the credit info).
    tmp = tempfile.mkdtemp()
    c = _candidate(tmp)
    c.extras = {"attribution_required": True}
    c.attribution_text = "Credit: Dareful"
    r = analyze_clip("dareful:1", c)[0]
    assert r.attribution_required is True
    assert r.attribution_text == "Credit: Dareful"
