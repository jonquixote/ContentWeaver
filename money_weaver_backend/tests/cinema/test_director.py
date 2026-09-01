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
