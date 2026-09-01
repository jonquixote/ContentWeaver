from typing import Literal

from pydantic import BaseModel, Field

from src.services.cinema.types import CameraMove, ShotScale

# Source identity survives into the cinema layer. Footage registry sources are
# NOT laundered into "local"; a provider-rotation penalty keys off this value.
Provider = Literal[
    "pexels", "pixabay", "local", "generative",
    "archive_org", "nasa_images", "loc", "wikimedia_commons", "open_images",
    "coverr", "pond5_pd",
    # manual-import / hand-pick sources
    "mixkit", "dareful", "life_of_vids", "splitshire", "videezy", "videvo",
    "pikwizard", "xstockvideo", "cdc", "nps", "eso", "esa_hubble",
    "motionelements",
]


class ClipRecord(BaseModel):
    clip_id: str
    provider: Provider
    source_url: str
    local_path: str | None = None
    duration_s: float | None = Field(default=None, gt=0.0)
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
