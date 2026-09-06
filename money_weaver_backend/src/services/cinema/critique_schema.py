from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ShotVerdict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_index: int = Field(ge=0)
    verdict: Literal["match", "mismatch"]
    reason: str = Field(min_length=1)


class RenderCritique(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shots: list[ShotVerdict]
    overall_verdict: Literal["pass", "review"]
    summary: str = Field(min_length=1)
