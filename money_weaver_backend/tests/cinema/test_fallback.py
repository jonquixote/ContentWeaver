import os

from src.services.video.stock_footage_service import StockFootageService


def test_rerank_with_cinema_returns_same_object_when_disabled(monkeypatch):
    monkeypatch.delenv("CINEMA_ENABLED", raising=False)
    svc = StockFootageService.__new__(StockFootageService)
    videos = [{"id": 1, "tags": "b", "alt": "a"}, {"id": 2, "tags": "d"}]
    result = svc.rerank_with_cinema(videos, spec=None)
    assert result is videos  # identity: byte-identical, untouched


def test_rerank_with_cinema_returns_same_object_when_flag_false(monkeypatch):
    monkeypatch.setenv("CINEMA_ENABLED", "false")
    svc = StockFootageService.__new__(StockFootageService)
    videos = [{"id": 1, "tags": "x"}]
    result = svc.rerank_with_cinema(videos, spec=None)
    assert result is videos


def test_rerank_with_cinema_does_not_crash_without_spec(monkeypatch):
    monkeypatch.setenv("CINEMA_ENABLED", "true")
    svc = StockFootageService.__new__(StockFootageService)
    videos = [{"id": 1, "tags": "x"}]
    try:
        result = svc.rerank_with_cinema(videos, spec=None)
        assert isinstance(result, list)
    except Exception as e:
        # must degrade, not raise, per never-block rule
        assert False, f"rerank_with_cinema should not raise: {e}"


def test_rerank_with_cinema_returns_list_when_enabled_and_spec(monkeypatch):
    monkeypatch.setenv("CINEMA_ENABLED", "true")
    from src.services.cinema.shot import ShotSpec
    svc = StockFootageService.__new__(StockFootageService)
    spec = ShotSpec(
        scene_number=1,
        shot_index=0,
        narrative_beats="jokes",
        subject_concrete="comedian with mic",
        scale="ms",
        move="static",
        function="context",
        mood="dim",
    )
    videos = [{"id": 1, "alt": "comedian on stage", "source": "pexels", "width": 1920, "height": 1080}]
    result = svc.rerank_with_cinema(videos, spec)
    assert isinstance(result, list)


def test_rerank_preserves_rank_order_and_stubbed_dedup(monkeypatch):
    # Stub build_clip_records with controlled average_hash values so dedup and
    # ranking actually exercise, then assert the returned order is the RANKED
    # order followed by unranked stragglers.
    monkeypatch.setenv("CINEMA_ENABLED", "true")
    from src.services.cinema.clip import ClipRecord
    from src.services.cinema.shot import ShotSpec
    from src.services.cinema.types import ShotScale

    svc = StockFootageService.__new__(StockFootageService)

    # 1 and 2 are near-dup (hash differs by 1 bit) and both MS -> one deduped.
    # 3 is a different subject (ELS) -> lower score, still ranked after MS.
    # 4 has a distinct hash -> kept as straggler if dropped, else ranked.
    records = [
        ClipRecord(clip_id="pexels:1", provider="pexels", source_url="u", duration_s=10,
                   scale=ShotScale.MS, average_hash="1111111111111111"),
        ClipRecord(clip_id="pexels:2", provider="pexels", source_url="u", duration_s=10,
                   scale=ShotScale.MS, average_hash="1111111111111110"),
        ClipRecord(clip_id="pexels:3", provider="pexels", source_url="u", duration_s=10,
                   scale=ShotScale.ELS, average_hash="aaaaaaaaaaaaaaaa"),
        ClipRecord(clip_id="pexels:4", provider="pexels", source_url="u", duration_s=10,
                   scale=ShotScale.MCU, average_hash="bbbbbbbbbbbbbbbb"),
    ]
    monkeypatch.setattr(svc, "build_clip_records", lambda v: records)

    spec = ShotSpec(
        scene_number=1, shot_index=0, narrative_beats="jokes",
        subject_concrete="comedian with mic", scale="ms", move="static",
        function="context", mood="dim",
    )
    videos = [{"id": i, "alt": "x", "source": "pexels"} for i in (1, 2, 3, 4)]
    result = svc.rerank_with_cinema(videos, spec)
    out_ids = [v["id"] for v in result]
    # neardup (2) is deduped out; ranked MS clips come before ELS; all present.
    assert 2 not in out_ids
    assert 1 in out_ids and 3 in out_ids and 4 in out_ids
    # rank order: MS (1) before ELS (3); stragglers (if any) appended after.
    assert out_ids.index(1) < out_ids.index(3)
    assert set(out_ids) == {1, 3, 4}


def test_rerank_with_cinema_chosen_excludes_near_dup(monkeypatch):
    # A clip chosen for an EARLIER shot (passed via `chosen`) must exclude its
    # near-dup from this shot's ranking through the public signature.
    monkeypatch.setenv("CINEMA_ENABLED", "true")
    from src.services.cinema.clip import ClipRecord
    from src.services.cinema.shot import ShotSpec
    from src.services.cinema.types import ShotScale

    svc = StockFootageService.__new__(StockFootageService)
    earlier = ClipRecord(clip_id="pexels:9", provider="pexels", source_url="u",
                         duration_s=10, scale=ShotScale.MS, average_hash="1111111111111111")
    records = [
        ClipRecord(clip_id="pexels:5", provider="pexels", source_url="u", duration_s=10.2,
                   scale=ShotScale.MS, average_hash="1111111111111110"),  # near-dup of earlier
        ClipRecord(clip_id="pexels:6", provider="pexels", source_url="u", duration_s=11,
                   scale=ShotScale.MS, average_hash="aaaaaaaaaaaaaaaa"),
    ]
    monkeypatch.setattr(svc, "build_clip_records", lambda v: records)

    spec = ShotSpec(
        scene_number=2, shot_index=0, narrative_beats="jokes",
        subject_concrete="comedian with mic", scale="ms", move="static",
        function="context", mood="dim",
    )
    videos = [{"id": 5, "alt": "x", "source": "pexels"}, {"id": 6, "alt": "y", "source": "pexels"}]
    result = svc.rerank_with_cinema(videos, spec, chosen=[earlier])
    out_ids = [v["id"] for v in result]
    assert 5 not in out_ids  # near-dup of the earlier clip excluded
    assert 6 in out_ids
