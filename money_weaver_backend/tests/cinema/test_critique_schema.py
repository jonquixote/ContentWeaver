import pytest
from pydantic import ValidationError
from src.services.cinema.critique_schema import RenderCritique, ShotVerdict


def test_shot_verdict_accepts_valid():
    v = ShotVerdict(shot_index=0, verdict="match", reason="comedian on stage, CU as specced")
    assert v.verdict == "match"


def test_shot_verdict_rejects_bad_verdict():
    with pytest.raises(ValidationError):
        ShotVerdict(shot_index=0, verdict="maybe", reason="x")


def test_render_critique_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        RenderCritique(shots=[], overall_verdict="pass", summary="ok", extra_field=1)


def test_render_critique_requires_shots_list():
    with pytest.raises(ValidationError):
        RenderCritique(overall_verdict="pass", summary="ok")
