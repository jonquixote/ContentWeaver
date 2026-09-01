# Cinema Plan B — Footage Ingest + ClipRecord Index

Date: 2026-08-31
Status: Design (pre-implementation)
Parent: 2026-08-31-cinema-engine-design.md. Amends docs/FOOTAGE_INGEST_SERVICE.md.
Scope: `money_weaver_backend/src/services/footage/` + `src/services/cinema/clip.py`.
Adds optional heavy deps (torch/onnx/open-clip, sqlite-vec) — all behind flags.

## Amended from FOOTAGE_INGEST_SERVICE.md

Two deviations from that spec, per the overview:

1. **VectorStore**: `pgvector` → `sqlite-vec` default (zero-provision dev/CI/
   single-node), pgvector only when `VECTOR_STORE=pgvector` is provisioned.
   One `VectorStore` interface (`upsert`, `query(vector,k,filters)`, `delete`).
2. **Embedder**: `Embedder` interface with backends `torch` (CPU), `onnxruntime`,
   `hosted_gemini`. `EMBED_BACKEND` selects. Default `none` (disabled) so tests
   pass with no model installed.

The rest of that spec is adopted verbatim: pipeline
`DISCOVER→FILTER→ACQUIRE→NORMALIZE→ANALYZE→INDEX`, adapter roster/waves,
license allowlist + provenance/render-credits, storage layout, analysis stage
(shot segmentation, embeddings, cinematographic attrs, dedup), schema
(`footage_assets`, `footage_shots`, `ingest_jobs`, `ingest_rejections`),
Celery `footage` queue tasks, config, retrieval API, rollout phases, tests.

## Deviations summary

| In FOOTAGE_INGEST_SERVICE.md | In Plan B |
|---|---|
| Embeddings: open-clip `ViT-L-14` | Embedder interface; default `ViT-B-32` for CPU/Intel; `ViT-L-14` reserved for `hosted_gemini`/GPU via `EMBED_BACKEND_L_MODEL` |
| Vector DB: pgvector (Supabase) | sqlite-vec default; pgvector optional via `VECTOR_STORE` |
| Shot scale enum numbers | reuse `cinema/types.py::ShotScale` (superset of the DTO) |

## Cinematographic attribute extraction

Runs on `proxy.mp4`: PySceneDetect shot segmentation (flagged
`USE_SCENEDETECT`, off by default → one clip per asset), open-clip embeddings,
face/person bbox → scale heuristic, Farneback optical flow → move/motion_energy,
k-means palette + luma, pHash dedup. Each detected shot → one `ClipRecord`.

## Config additions

```
VECTOR_STORE=sqlite_vec            # sqlite_vec | pgvector
EMBED_BACKEND=none                 # none | torch | onnx | hosted_gemini
EMBED_MODEL=ViT-B-32               # CPU/Intel default; ViT-L-14 only via hosted_gemini or GPU
EMBED_BACKEND_L_MODEL=ViT-L-14     # hosted/GPU option, never CPU default
USE_SCENEDETECT=false
ENABLE_BLIP=false
FOOTAGE_SOURCES_ENABLED=pexels,pixabay,coverr,archive_org,nasa,loc,wikimedia_commons
FOOTAGE_MAX_DURATION_S=600
FOOTAGE_QUEUE=footage
```

## Acceptance

- VectorStore conformance suite passes on sqlite-vec (and pgvector when set).
- With `EMBED_BACKEND=none`, ingest still produces ClipRecords (typed fields,
  embeddings None) — no crash; test suite green.
- License gate rejects unknown/unallowlisted assets; 100% of ingested assets
  carry provenance + attribution where CC-BY/Coverr.
- Retrieval ranking returns ClipRecords with `embedding` present when a backend
  is on; gracefully empty embeddings when not.

## Non-goals

- No montage/critic changes here. No TTS/captions. No ComfyUI/Wan.
- youtube_cc + pond5 deferred (Wave Later per FOOTAGE_INGEST_SERVICE §11).
