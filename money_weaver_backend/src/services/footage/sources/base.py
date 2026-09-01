from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CandidateVideo:
    source: str                 # adapter name, e.g. "archive_org"
    source_id: str              # stable identifier at source
    title: str
    description: str | None
    tags: list[str]
    subjects: list[str]
    creator: str | None
    published_at: datetime | None
    duration_s: float | None
    width: int | None
    height: int | None
    download_url: str           # direct file URL (best reasonable quality)
    page_url: str               # canonical page, for provenance/attribution
    license_spdx: str | None    # "CC0-1.0", "public-domain", ...
    license_raw: str | None
    attribution_text: str | None
    extras: dict = field(default_factory=dict)


@dataclass
class SearchPage:
    candidates: list[CandidateVideo]
    next_cursor: str | None = None


class BaseFootageSource(ABC):
    """Metadata-only adapter. search() must NOT download. Adapters opt into
    attribution via CREDIT_ATTRIBUTION; strengths come from VIDEO_SOURCES.md."""

    name: str
    CREDIT_ATTRIBUTION: bool = False
    strengths: list[str] = []

    @abstractmethod
    def search(self, query: str, *, limit: int = 100, cursor: str | None = None) -> SearchPage:
        ...

    @abstractmethod
    def get_metadata(self, source_id: str) -> CandidateVideo:
        ...

    @abstractmethod
    def resolve_download(self, source_id: str) -> str:
        ...
