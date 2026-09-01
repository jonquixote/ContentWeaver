from typing import Literal

from pydantic import BaseModel, Field

from src.services.cinema.types import CameraMove, ShotScale


class ClipRecord(BaseModel):
    clip_id: str
    provider: Literal["pexels", "pixabay", "local", "generative"]
    source_url: str
    local_path: str | None = None
    duration_s: float = Field(gt=0.0)
    width: int | None = None
    height: int | None = None
    embedding: list[float] | None = None
    caption: str | None = None
    scale: ShotScale | None = None
    move: CameraMove | None = None
    palette: list[str] | None = None
    luminance: float | None = None
    motion_energy: float | None = None
    faces: int | None = None
    average_hash: str | None = None
    used_in_video_ids: list[str] = []
    attribution_required: bool = False
    attribution_text: str | None = None
