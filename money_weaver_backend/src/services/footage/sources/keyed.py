from __future__ import annotations

from src.services.footage.sources.base import BaseFootageSource, CandidateVideo, SearchPage


class Pond5PDSource(BaseFootageSource):
    name = "pond5_pd"
    CREDIT_ATTRIBUTION = False
    strengths = ["archival pd footage", "animations", "nasa mirrors"]

    def search(self, query: str, *, limit: int = 100, cursor: str | None = None) -> SearchPage:
        raise NotImplementedError("requires free download account; verify believed-PD per clip")

    def get_metadata(self, source_id: str) -> CandidateVideo:
        raise NotImplementedError

    def resolve_download(self, source_id: str) -> str:
        raise NotImplementedError
