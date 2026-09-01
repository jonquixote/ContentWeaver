#!/usr/bin/env python
"""Live Plan B ingest driver (non-CI). Serial + polite.

Sets EMBED_BACKEND=torch, iterates the real keyless sources (archive_org, pexels,
pixabay, nasa_images), driving ~12 seed-queries each built from the adapter's
strengths tags, calling discover(). License gate + duration guard apply inside
discover(). Writes to FOOTAGE_ASSETS_DB (default app.db) for the acceptance gate.

Usage: EMBED_BACKEND=torch python scripts/footage_drive_ingest.py [--source S] [--limit N]
"""
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "money_weaver_backend"))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("EMBED_BACKEND", "torch")
os.environ.setdefault("FOOTAGE_ASSETS_DB", os.path.join(ROOT, "src", "database", "app.db"))
os.environ.setdefault("FOOTAGE_VECTOR_DB", os.environ["FOOTAGE_ASSETS_DB"])

QUERIES_PER_SOURCE = int(os.getenv("FOOTAGE_QUERIES_PER_SOURCE", "12"))
POLITE_SLEEP_S = float(os.getenv("FOOTAGE_POLITE_SLEEP_S", "1.5"))

# Seed queries per source, drawn from strengths-tag vocabulary + generic terms.
SEED_QUERIES = {
    "archive_org": ["aerial coastline", "empty factory floor", "city street 1950s",
                    "newsreel parade", "home movie beach", "early cinema train",
                    "stock footage office", "vintage car", "factory smoke",
                    "children playing street", "airplane flyover", "wheat field"],
    "pexels": ["aerial coastline", "people laughing cafe", "modern office team",
               "city night traffic", "portrait talking", "product closeup",
               "mountain drone", "beach waves", "concert crowd", "hands typing",
               "sunset skyline", "running city"],
    "pixabay": ["aerial coastline", "nature forest", "abstract light", "drone beach",
                "city timelapse", "fireworks night", "ocean waves", "mountain fog",
                "forest path", "rain window", "desert dunes", "neon abstract"],
    "nasa_images": ["earth from orbit", "rocket launch", "ISS spacewalk", "moon surface",
                    "mars rover", "solar flare", "telescope observatory", "stars nebula",
                    "spacewalk repair", "reentry capsule", "earth hurricane", "satellite deploy"],
}


def drive(source: str, limit: int) -> int:
    from src.services.footage.ingest import discover
    from src.services.footage.sources.registry import get_source

    src = get_source(source)
    queries = SEED_QUERIES.get(source, []) or list(src.strengths)
    queries = (queries or [])[:QUERIES_PER_SOURCE]
    total = 0
    for q in queries:
        try:
            n = discover(source, q, limit=limit)
            total += n
            print(f"  [{source}] q={q!r} -> enqueued {n} (running total {total})",
                  flush=True)
        except NotImplementedError:
            print(f"  [{source}] q={q!r} -> SKIP (search not wired)")
            break
        except Exception as e:
            print(f"  [{source}] q={q!r} -> ERROR {e}")
        time.sleep(POLITE_SLEEP_S)
    return total


def main():
    args = [a for a in sys.argv[1:]]
    source_override = None
    limit = int(os.getenv("FOOTAGE_PAGE_LIMIT", "100"))
    if "--source" in args:
        source_override = args[args.index("--source") + 1]
    sources = [source_override] if source_override else ["archive_org", "pexels", "pixabay", "nasa_images"]
    grand = 0
    for s in sources:
        print(f"=== driving {s} ===", flush=True)
        grand += drive(s, limit)
    print(f"DONE: {grand} assets enqueued across {sources}", flush=True)


if __name__ == "__main__":
    main()
