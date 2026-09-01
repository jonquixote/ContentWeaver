from __future__ import annotations

from src.services.footage.sources.base import BaseFootageSource, CandidateVideo, SearchPage


class _KeylessAPI(BaseFootageSource):
    """Base for the keyless-API wave. Subclasses pull JSON/REST/OAI-PMH.
    Real search() bodies are wired per-source in the ingest phase; here the
    contract + strengths + attribution flag are set so the registry is
    engine-readable and the unit suite stays network-free."""

    def search(self, query: str, *, limit: int = 100, cursor: str | None = None) -> SearchPage:
        raise NotImplementedError  # wired per source during ingest

    def get_metadata(self, source_id: str) -> CandidateVideo:
        raise NotImplementedError

    def resolve_download(self, source_id: str) -> str:
        raise NotImplementedError


class ArchiveOrgSource(_KeylessAPI):
    name = "archive_org"
    CREDIT_ATTRIBUTION = False
    strengths = ["old films", "newsreels", "ads", "home movies", "prelinger", "public domain"]


class NasaImagesSource(_KeylessAPI):
    name = "nasa_images"
    CREDIT_ATTRIBUTION = False
    strengths = ["space", "rockets", "earth from orbit", "science"]


class LocSource(_KeylessAPI):
    name = "loc"
    CREDIT_ATTRIBUTION = False
    strengths = ["early cinema", "americana", "newsreels", "national film registry"]


class WikimediaCommonsSource(_KeylessAPI):
    name = "wikimedia_commons"
    CREDIT_ATTRIBUTION = True
    strengths = ["places", "animals", "objects", "encyclopedic b-roll"]


class OpenImagesSource(_KeylessAPI):
    name = "open_images"
    CREDIT_ATTRIBUTION = False
    strengths = ["dutch/european newsreels", "archival film", "rich metadata"]


class PexelsSource(_KeylessAPI):
    name = "pexels"
    CREDIT_ATTRIBUTION = False
    strengths = ["lifestyle", "people", "modern b-roll"]


class PixabaySource(_KeylessAPI):
    name = "pixabay"
    CREDIT_ATTRIBUTION = False
    strengths = ["wide variety", "nature", "abstract"]


class CoverrSource(_KeylessAPI):
    name = "coverr"
    CREDIT_ATTRIBUTION = True
    strengths = ["website hero loops", "tech", "product"]
