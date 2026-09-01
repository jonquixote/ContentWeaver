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
