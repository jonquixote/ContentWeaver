from __future__ import annotations

import os

from src.services.footage.sources.base import BaseFootageSource


def _reg():
    # Imported lazily so importing registry has no keyless/keyed side effects.
    from src.services.footage.sources import keyed, keyless
    return {
        "archive_org": keyless.ArchiveOrgSource,
        "nasa_images": keyless.NasaImagesSource,
        "loc": keyless.LocSource,
        "wikimedia_commons": keyless.WikimediaCommonsSource,
        "open_images": keyless.OpenImagesSource,
        "pexels": keyless.PexelsSource,
        "pixabay": keyless.PixabaySource,
        "coverr": keyless.CoverrSource,
        "pond5_pd": keyed.Pond5PDSource,
    }


SOURCE_REGISTRY: dict[str, type[BaseFootageSource]] = _reg()


def get_source(name: str) -> BaseFootageSource:
    return SOURCE_REGISTRY[name]()


def enabled_sources() -> list[BaseFootageSource]:
    enabled = (os.getenv("FOOTAGE_SOURCES_ENABLED", "") or "").split(",")
    out = []
    for name, cls in SOURCE_REGISTRY.items():
        if name in enabled:
            out.append(cls())
    return out


def describe_sources() -> list[dict]:
    return [
        {"name": name, "strengths": list(cls.strengths),
         "credit_attribution": cls.CREDIT_ATTRIBUTION}
        for name, cls in SOURCE_REGISTRY.items()
    ]
