import os

from src.services.cinema.director_service import (
    build_director_prompt,
    keyword_to_scale,
    parse_director_json,
)
from src.services.cinema.types import ShotScale


def test_build_prompt_rejects_abstract_nouns():
    prompt = build_director_prompt("wealth personifies success", "a rich man's story")
    assert "abstract" in prompt.lower()
    assert "concrete" in prompt.lower()
    # the concrete-subject rule is present (worded as 'Never use abstract nouns')
    assert "never use abstract" in prompt.lower()


def test_keyword_to_scale_maps():
    assert keyword_to_scale("close-up face") == ShotScale.CU
    assert keyword_to_scale("city skyline") in (ShotScale.LS, ShotScale.ELS)
    assert keyword_to_scale("room interior") == ShotScale.MS
    assert keyword_to_scale("") == ShotScale.MS  # default


def test_parse_director_json_returns_shotspecs():
    raw = (
        '{"shots":[{"shot_index":0,"narrative_beats":"jokes fly",'
        '"subject_concrete":"comedian with microphone on stage",'
        '"scale":"ms","move":"static","function":"establish",'
        '"mood":"dim","screen_direction":"neutral","intensity":0.4,'
        '"target_duration_s":2.5}]}'
    )
    specs = parse_director_json(raw)
    assert specs is not None
    assert len(specs) == 1
    assert specs[0].scale == ShotScale.MS
    assert specs[0].subject_concrete == "comedian with microphone on stage"


def test_parse_director_json_handles_garbage():
    assert parse_director_json("not json") is None or parse_director_json("not json") == []


from src.services.cinema.director_service import deterministic_director, run_director


def _failing_llm(*args, **kwargs):
    raise RuntimeError("quota exhausted")


def test_deterministic_director_never_empty():
    specs = deterministic_director(
        "A wealthy man confronts his fear on a city street at night",
        scene_number=3,
        shot_count_hint=3,
    )
    assert len(specs) >= 1
    for s in specs:
        assert s.subject_concrete  # concrete-subject rule holds even deterministically
        assert s.scale is not None
        assert s.move is not None


def test_run_director_falls_back_when_llm_down(monkeypatch):
    monkeypatch.setenv("CINEMA_CACHE_DIR", "/tmp/cw-cinema-cache-fallback-test")
    specs = run_director(
        "close-up of a nervous comedian",
        scene_number=1,
        story_context="comedy club",
        llm_fn=_failing_llm,
    )
    assert specs
    assert all(s.subject_concrete for s in specs)


def test_run_director_uses_llm_success(monkeypatch):
    monkeypatch.setenv("CINEMA_DIRECTOR_ENABLED", "true")
    monkeypatch.setenv("CINEMA_CACHE_DIR", "/tmp/cw-cinema-cache-llm-test")

    def ok_llm(prompt, model=None, **kw):
        return (
            '{"shots":[{"shot_index":0,"narrative_beats":"jokes",'
            '"subject_concrete":"comedian with mic on stage","scale":"mcu",'
            '"move":"dolly_in","function":"context","mood":"warm",'
            '"intensity":0.6,"target_duration_s":3.0}]}'
        )
    specs = run_director("unique-llm-scene-text", 1, story_context="s", llm_fn=ok_llm)
    assert len(specs) == 1
    assert specs[0].scale.value == "mcu"


def test_cache_key_salted_by_director_version(monkeypatch):
    # A stale cache entry (written under a previous DIRECTOR_VERSION) must not
    # be reused: the key salt changes on version bump.
    from src.services.cinema import director_service as ds
    from src.services.cinema.director_service import _cache_key

    monkeypatch.setattr(ds, "DIRECTOR_VERSION", "a1")
    k1 = _cache_key("same scene text")
    monkeypatch.setattr(ds, "DIRECTOR_VERSION", "a2")
    k2 = _cache_key("same scene text")
    assert k1 != k2
