from typing import Literal

from pydantic import BaseModel, Field

from src.services.cinema.types import CameraMove, ShotFunction, ShotScale


class ShotSpec(BaseModel):
    scene_number: int
    shot_index: int
    narrative_beats: str
    subject_concrete: str
    scale: ShotScale
    move: CameraMove
    function: ShotFunction
    mood: str
    screen_direction: Literal["L2R", "R2L", "neutral"] = "neutral"
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    target_duration_s: float = Field(default=2.5, gt=0.0)
    avoid_clip_ids: list[str] = []
