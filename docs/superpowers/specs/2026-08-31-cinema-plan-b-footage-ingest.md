# Cinema Plan B — Footage Ingest + ClipRecord Index

Date: 2026-08-31 (amended 2026-09-01)
Status: Design (pre-implementation)
Parent: 2026-08-31-cinema-engine-design.md. Amends docs/FOOTAGE_INGEST_SERVICE.md.
Canonical source inventory: docs/VIDEO_SOURCES.md (supersedes the ingest spec's
seven-source list).
Scope: `money_weaver_backend/src/services/footage/` + `src/services/cinema/clip.py`.
Adds optional heavy deps (torch/onnx/open-clip, sqlite-vec) — all behind flags.

## Amended from FOOTAGE_INGEST_SERVICE.md

Standing constraints unchanged:
- **VectorStore**: `sqlite-vec` default (zero-provision dev/CI/single-node), pgvector
  only when `VECTOR_STORE=pgvector` is provisioned. One `VectorStore` interface
  (`upsert`, `query(vector,k,filters)`, `delete`).
- **Embedder**: `Embedder` interface with backends `torch` (CPU), `onnxruntime`,
  `hosted_gemini`. `EMBED_BACKEND` selects; default `none` (disabled) so tests
  pass with no model installed. Default model `ViT-B-32` (CPU/Intel); `ViT-L-14`
  reserved for hosted/GPU via `EMBED_BACKEND_L_MODEL`.
- Pipeline `DISCOVER→FILTER→ACQUIRE→NORMALIZE→ANALYZE→INDEX`, storage layout,
  analysis stage, schema, Celery `footage` queue, retrieval API, acceptance
  gates (1,000 assets / ≥3 sources / license gate / "aerial coastline" sanity on
  the labeled 200-shot set).

## Amendments (2026-09-01) — adapter set reconciled to VIDEO_SOURCES.md

### A1 — Two adapter classes (no fragile scrapers)
Split the adapter surface into two classes:
1. **API adapters** (`footage/sources/apibase.py`) — keyless-API wave (Phase 0/1):
   `archive_org`, `nasa_images`, `loc`, `wikimedia_commons`, `open_images`,
   `pexels`, `pixabay`, `coverr`. Implemented against their JSON/REST/OAI-PMH APIs.
2. **Manual-import drop path** (`footage/importers.py`) — the scrape/hand-pick
   tier (Mixkit, Dareful, Life of Vids, Splitshire, Videezy, Videvo, PikWizard,
   XStockvideo, CDC, NPS, ESO, ESA/Hubble, MotionElements PD, Beachfront via
   archive_org, etc.). NO scrapers. A human (or an offline downloader) drops a
   local file or URL; the importer runs the SAME analyzer + writes to the SAME
   index. Each item carries a sourced `license_spdx` + `attribution_required`.

### A2 — Provenance fields + render-time credits manifest
- `footage_assets` gains `attribution_required: bool` and `attribution_text`.
  Derived from VIDEO_SOURCES.md "CREDIT LIST" (Dareful, Mazwai CC, Videezy free,
  Videvo attribution clips, Vidsplay, Motion Places, CuteStockFootage, Free Stock
  Footage Archive, ESO, ESA/Hubble, Coverr, Wikimedia CC-BY, YouTube/Vimeo CC-BY,
  Freepik free, Vecteezy free) vs "NO-CREDIT LIST" (Archive.org PD, NASA, LoC
  free-to-use, Smithsonian CC0, MotionElements PD, NPS, CDC, Mixkit, Pexels,
  Pixabay, Life of Vids, Splitshire, PikWizard, XStockvideo). Each adapter opts
  in via a `CREDIT_ATTRIBUTION: bool` class attr; per-video attribution_text set
  from the doc.
- New `credits_manifest(video_used_clips: list[ClipRecord]) -> list[dict]`
  emitted at render time (assembly_service) — collects every used shot's
  `attribution_required` + `attribution_text`, and appends a credits card /
  description block when any require attribution.

### A3 — Pond5 PD in the keyed wave; YouTube/Vimeo CC-BY deferred
- **Pond5 Public Domain Project** stays in the **keyed** (Wave Next) adapter set —
  free PD archival, but requires a free download account. Read the per-clip
  "Believed PD" flag and verify; treat uncertain as rejected.
- **YouTube CC / Vimeo CC-BY remain deferred** (Wave Later) on quota — no bulk
  path; a trickle, not a pool. Not built in Plan B.

### A4 — Machine-readable `strengths` tags on registry entries
Each registry entry carries `strengths: list[str]` from the doc's "Has:" notes
("old films", "space", "early cinema", "lifestyle", "travel", "drone", "nature",
"tech", "health", "newsreels", ...). Used later for niche-aware source weighting
(Plan C). Stored on the adapter class; surfaced in `registry.describe()`.

## Adapter set (reconciled)

| Wave | Class | Adapters | strengths |
|---|---|---|---|
| Phase 0/1 keyless API | APIAdapter | archive_org, nasa_images, loc, wikimedia_commons, open_images | old films/newsreels, space, early cinema, encyclopedic b-roll, Dutch/EU archival |
| Phase 0/1 keyless API (already wired) | APIAdapter | pexels, pixabay, coverr | lifestyle/people, nature/abstract, tech/product |
| Manual import | importer | Mixkit, Dareful, Life of Vids, Splitshire, Videezy, Videvo, PikWizard, XStockvideo, CDC, NPS, ESO, ESA/Hubble, MotionElements PD, Beachfront via archive_org | travel/nature/drone, people/nature, lifestyle/urban, cinematic, motion graphics, health, parks, telescopes, PD static set |
| Wave Next (free key) | APIAdapter | europeana, nara, dpla, smithsonian_oa | European heritage, US gov/military, US history, museum/science |
| Wave Later (constrained) | APIAdapter | pond5_pd | archival PD (verify); requires free account |

Deferred: youtube_cc, vimeo_cc (quota); freepik, vecteezy (attribution, free
tier); publicdomainfootage.com, footagefarm (paid) — not built.

## Config additions

```
VECTOR_STORE=sqlite_vec            # sqlite_vec | pgvector
EMBED_BACKEND=none                 # none | torch | onnx | hosted_gemini
EMBED_MODEL=ViT-B-32               # CPU/Intel default; ViT-L-14 only via hosted_gemini or GPU
EMBED_BACKEND_L_MODEL=ViT-L-14     # hosted/GPU option, never CPU default
USE_SCENEDETECT=false
ENABLE_BLIP=false
FOOTAGE_SOURCES_ENABLED=pexels,pixabay,coverr,archive_org,nasa_images,loc,wikimedia_commons,open_images
FOOTAGE_MANUAL_IMPORT_DIR=footage/imports
FOOTAGE_MAX_DURATION_S=600
FOOTAGE_QUEUE=footage
FOOTAGE_DISK_RETENTION_H=1         # purge work/ video+audio older than this before ingest/render
```

## Acceptance

- VectorStore conformance suite passes on sqlite-vec (and pgvector when set).
- With `EMBED_BACKEND=none`, ingest still produces ClipRecords (typed fields,
  embeddings None) — no crash; test suite green.
- License gate rejects unknown/unallowlisted assets; 100% of ingested assets
  carry provenance + `attribution_required`/`attribution_text`; ND (no-credit)
  sources carry `attribution_required=false`.
- Manual-import path drives the same analyzer + index as the API adapters
  (single shared code path).
- credits_manifest emits correctly for a mixed credit/no-credit clip mix.
- Registry entries expose `strengths` (engine-readable); Pond5 PD present;
  YouTube/Vimeo absent.
- 1,000 assets / ≥3 sources imported; license gate holds; "aerial coastline"
  sanity on the labeled 200-shot set.
- Disk-cleanup policy is a first-class task (FOOTAGE_DISK_RETENTION_H).

## Non-goals

- No montage/critic changes here. No TTS/captions. No ComfyUI/Wan.
- No scrapers (manual-import only for the hand-pick tier).
- youtube_cc, vimeo_cc, freepik, vecteezy, publicdomainfootage.com, footagefarm
  deferred (quota / attribution / paid).
