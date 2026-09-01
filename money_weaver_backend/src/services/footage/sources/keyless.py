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
                download_url="",  # NOT speculative; resolved via metadata API in resolve_download
                page_url=f"https://archive.org/details/{cid}",
                license_spdx=spdx,
                license_raw=doc.get("licenseurl"),
                attribution_text=None,
                extras={},
            ))
        return SearchPage(candidates=cands, next_cursor=None)

    def resolve_download(self, source_id: str) -> str:
        """Enumerate the item's actual files via the archive.org metadata API
        and pick the first playable MP4. The old '{id}/{id}.mp4' guess rarely
        exists — mass 404s. Returns '' when no MP4 is found."""
        import requests
        r = requests.get(f"https://archive.org/metadata/{source_id}", timeout=20)
        r.raise_for_status()
        files = r.json().get("files", [])
        for f in files:
            name = f.get("name", "").lower()
            if name.endswith(".mp4"):
                return f"https://archive.org/download/{source_id}/{f['name']}"
        return ""


class NasaImagesSource(_KeylessAPI):
    name = "nasa_images"
    CREDIT_ATTRIBUTION = False
    strengths = ["space", "rockets", "earth from orbit", "science"]

    def search(self, query: str, *, limit: int = 100, cursor: str | None = None) -> SearchPage:
        import requests
        params = {
            "q": query,
            "media_type": "video",
            "page_size": min(limit, 100),
        }
        r = requests.get("https://images-api.nasa.gov/search", params=params, timeout=20)
        r.raise_for_status()
        items = r.json().get("collection", {}).get("items", [])
        cands = []
        for item in items:
            data = (item.get("data") or [{}])[0]
            nasa_id = data.get("nasa_id")
            if not nasa_id:
                continue
            # NASA media guidelines: public domain, use-nasa-media-guidelines.
            cands.append(CandidateVideo(
                source=self.name,
                source_id=nasa_id,
                title=data.get("title") or nasa_id,
                description=data.get("description"),
                tags=data.get("keywords") or [],
                subjects=[],
                creator=None,
                published_at=data.get("date_created"),
                duration_s=None,  # NASA search metadata exposes no duration; follow-up populate
                width=None,
                height=None,
                download_url=f"https://images-assets.nasa.gov/video/{nasa_id}/{nasa_id}~mobile.mp4",
                page_url=f"https://images.nasa.gov/details/{nasa_id}",
                license_spdx="nasa-media-guidelines",
                license_raw="NASA media guidelines (public domain)",
                attribution_text=None,
                extras={},
            ))
        return SearchPage(candidates=cands, next_cursor=None)


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

    def search(self, query: str, *, limit: int = 100, cursor: str | None = None) -> SearchPage:
        import os
        import requests
        api_key = os.getenv("PEXELS_API_KEY", "")
        if not api_key:
            return SearchPage(candidates=[], next_cursor=None)
        params = {"query": query, "per_page": min(limit, 80)}
        r = requests.get(
            "https://api.pexels.com/videos/search",
            params=params,
            headers={"Authorization": api_key},
            timeout=20,
        )
        r.raise_for_status()
        cands = []
        for v in r.json().get("videos", []):
            # prefer an HD vertical-capable file; fall back to the first file
            files = v.get("video_files") or []
            best = next((f for f in files if f.get("quality") == "hd" and f.get("width", 0) >= 1080), None) or (files[0] if files else {})
            cands.append(CandidateVideo(
                source=self.name,
                source_id=str(v.get("id")),
                title=v.get("url") or v.get("id"),
                description=None,
                tags=(v.get("tags") or "").split(",") if isinstance(v.get("tags"), str) else [],
                subjects=[],
                creator=None,
                published_at=None,
                duration_s=v.get("duration"),
                width=v.get("width"),
                height=v.get("height"),
                download_url=best.get("link", ""),
                page_url=v.get("url", ""),
                license_spdx="LicenseRef-Pexels",
                license_raw="Pexels API — free to use",
                attribution_text=None,
                extras={},
            ))
        return SearchPage(candidates=cands, next_cursor=None)


class PixabaySource(_KeylessAPI):
    name = "pixabay"
    CREDIT_ATTRIBUTION = False
    strengths = ["wide variety", "nature", "abstract"]

    def search(self, query: str, *, limit: int = 100, cursor: str | None = None) -> SearchPage:
        import os
        import requests
        api_key = os.getenv("PIXABAY_API_KEY", "")
        if not api_key:
            return SearchPage(candidates=[], next_cursor=None)
        params = {"key": api_key, "q": query, "per_page": max(3, min(limit, 200))}
        r = requests.get("https://pixabay.com/api/videos/", params=params, timeout=20)
        r.raise_for_status()
        cands = []
        for v in r.json().get("hits", []):
            videos = v.get("videos") or {}
            url = videos.get("large", {}).get("url") or videos.get("medium", {}).get("url") or ""
            cands.append(CandidateVideo(
                source=self.name,
                source_id=str(v.get("id")),
                title=v.get("tags", ""),
                description=None,
                tags=(v.get("tags") or "").split(", ") if isinstance(v.get("tags"), str) else [],
                subjects=[],
                creator=None,
                published_at=None,
                duration_s=v.get("duration"),
                width=None,
                height=None,
                download_url=url,
                page_url=v.get("pageURL", ""),
                license_spdx="LicenseRef-Pixabay",
                license_raw="Pixabay — free to use",
                attribution_text=None,
                extras={},
            ))
        return SearchPage(candidates=cands, next_cursor=None)


class CoverrSource(_KeylessAPI):
    name = "coverr"
    CREDIT_ATTRIBUTION = True
    strengths = ["website hero loops", "tech", "product"]
