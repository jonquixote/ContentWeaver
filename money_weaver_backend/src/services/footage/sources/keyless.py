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

    def search(self, query: str, *, limit: int = 100, cursor: str | None = None) -> SearchPage:
        import requests
        params = {
            "q": query,
            "fl[]": ["identifier", "title", "description", "licenseurl", "mediatype"],
            "rows": limit,
            "output": "json",
        }
        r = requests.get(
            "https://archive.org/advancedsearch.php", params=params, timeout=20
        )
        r.raise_for_status()
        docs = r.json().get("response", {}).get("docs", [])
        cands = []
        for doc in docs:
            lic = (doc.get("licenseurl") or "").lower()
            spdx = "public-domain" if ("publicdomain" in lic or "creativecommons.org/publicdomain" in lic) else None
            if "creativecommons.org/licenses/by" in lic and "sa" in lic:
                spdx = "CC-BY-SA-4.0"
            elif "creativecommons.org/licenses/by/4.0" in lic:
                spdx = "CC-BY-4.0"
            elif "creativecommons.org/licenses/by/3.0" in lic:
                spdx = "CC-BY-3.0"
            elif "creativecommons.org/publicdomain/zero" in lic or "cc0" in lic:
                spdx = "CC0-1.0"
            cid = doc.get("identifier")
            if not cid:
                continue
            # Metadata-only; license_gate filters spdx None (unknown -> reject).
            cands.append(CandidateVideo(
                source=self.name,
                source_id=cid,
                title=doc.get("title") or cid,
                description=doc.get("description"),
                tags=[],
                subjects=[],
                creator=None,
                published_at=None,
                duration_s=None,
                width=None,
                height=None,
                download_url=f"https://archive.org/download/{cid}/{cid}.mp4",
                page_url=f"https://archive.org/details/{cid}",
                license_spdx=spdx,
                license_raw=doc.get("licenseurl"),
                attribution_text=None,
                extras={},
            ))
        return SearchPage(candidates=cands, next_cursor=None)


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
