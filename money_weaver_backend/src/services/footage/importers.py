from __future__ import annotations

import hashlib
import os

from src.services.footage.sources.base import CandidateVideo


class ManualImportError(Exception):
    pass


LICENSE_ALLOWLIST = {
    "CC0-1.0", "public-domain", "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-4.0",
    "LicenseRef-Pexels", "LicenseRef-Pixabay", "LicenseRef-Coverr",
    "LicenseRef-Mixkit", "LicenseRef-LifeOfVids", "LicenseRef-Splitshire",
    "LicenseRef-PikWizard", "LicenseRef-XStockvideo", "nasa-media-guidelines",
    "LicenseRef-Videvo-ATT", "LicenseRef-CDC", "LicenseRef-NPS",
    "LicenseRef-ESO", "LicenseRef-ESA-Hubble",
}


class ManualImporter:
    """Human-dropped file/URL -> same CandidateVideo shape -> same analyzer +
    index as the API adapters. No scraping. The importer only records metadata;
    the pipeline (normalize/analyze/index) is identical to API-sourced assets."""

    def __init__(self):
        self.allowlist = LICENSE_ALLOWLIST

    def import_path(
        self,
        path_or_url: str,
        source: str,
        license_spdx: str | None,
        *,
        attribution_required: bool = False,
        attribution_text: str | None = None,
        title: str | None = None,
    ) -> CandidateVideo:
        if not license_spdx or license_spdx not in self.allowlist:
            raise ManualImportError(
                f"license {license_spdx!r} not allowlisted; refusing to ingest"
            )
        if path_or_url.startswith("http"):
            source_id = f"{source}:sha1:{hashlib.sha1(path_or_url.encode()).hexdigest()}"
            page_url = path_or_url
        else:
            if not os.path.exists(path_or_url):
                raise ManualImportError(f"path not found: {path_or_url}")
            stat = os.stat(path_or_url)
            source_id = f"{source}:manual:{stat.st_ino}:{stat.st_size}"
            page_url = "file://" + os.path.abspath(path_or_url)
        return CandidateVideo(
            source=source,
            source_id=source_id,
            title=title or (path_or_url.rsplit("/", 1)[-1] if "/" in path_or_url else path_or_url),
            description=title,
            tags=[],
            subjects=[],
            creator=None,
            published_at=None,
            duration_s=None,
            width=None,
            height=None,
            download_url=path_or_url,
            page_url=page_url,
            license_spdx=license_spdx,
            license_raw=license_spdx,
            attribution_text=attribution_text,
            extras={"attribution_required": attribution_required},
        )

    def run(self, item: CandidateVideo) -> None:
        """Enqueue into the same normalize/analyze/index pipeline as API clients."""
        from src.services.footage.ingest import enqueue_acquire  # wired in Task 6
        enqueue_acquire(item)
