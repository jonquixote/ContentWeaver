# Footage Ingest Service — Implementation Spec

**Status:** Draft
**Date:** 2026-08-31
**Scope:** `money_weaver_backend` — new `src/services/footage/` package, replacing runtime keyword queries to Pexels/Pixabay as the primary footage path for `assembly_service.py`.

---

## 1. Purpose

Today `stock_footage_service.py` queries Pexels and Pixabay at assembly time with abstract text queries and accepts their relevance ranking. Consequences observed in production:

- Repeated, near-duplicate clips across videos (small effective pool per query).
- Abstract queries return generic lifestyle b-roll ("smiling face, straight to camera") that matches keywords but not scene intent.
- No per-shot cinematographic metadata (shot size, camera motion, duration, faces), so no montage logic is possible downstream.

**Goal:** build an owned, continuously growing footage corpus — multi-source, license-gated, normalized, embedded, and shot-annotated — that `assembly_service` queries by semantic similarity + cinematographic filters instead of keyword search.

Non-goals for this spec: the montage/editing engine itself (consumes this service's metadata later); music, TTS, captions.

---

## 2. Architecture

Linear ingest pipeline, one Celery task per stage, idempotent at each stage:

```
DISCOVER ──▶ FILTER ──▶ ACQUIRE ──▶ NORMALIZE ──▶ ANALYZE ──▶ INDEX
(search     (license    (download   (transcode,   (shots,      (pgvector,
 adapters)   allowlist)  to object   proxies,      embeddings,  queryable by
                        storage)    keyframes)    dedup)       assembly)
```

- **Package:** `money_weaver_backend/src/services/footage/`
- **Adapters:** mirror the existing `src/services/providers/` pattern — `base.py` (abstract source), `registry.py` (name → adapter), one module per source.
- **Queueing:** Celery via the existing `celery_app.py`; new queue `footage` so ingest never starves render jobs.
- **Storage:** existing `src/services/storage/` abstraction; layout in §5.
- **Index:** Postgres + pgvector (Supabase) — see schema in §7.

---

## 3. Source Adapters

### 3.1 Interface (`footage/sources/base.py`)

```python
@dataclass
class CandidateVideo:
    source: str                # adapter name, e.g. "archive_org"
    source_id: str             # stable identifier at source
    title: str
    description: str | None
    tags: list[str]
    subjects: list[str]
    creator: str | None
    published_at: datetime | None
    duration_s: float | None
    width: int | None
    height: int | None
    download_url: str          # direct file URL (best reasonable quality)
    page_url: str              # canonical page, for provenance/attribution
    license_spdx: str | None   # "CC0-1.0", "CC-BY-4.0", "public-domain", ...
    license_raw: str | None    # source's original license string
    attribution_text: str | None
    extras: dict               # source-specific metadata, stored raw

class BaseFootageSource(ABC):
    name: str
    @abstractmethod
    def search(self, query: str, *, limit: int = 100, cursor: str | None = None) -> SearchPage: ...
    @abstractmethod
    def get_metadata(self, source_id: str) -> CandidateVideo: ...
    @abstractmethod
    def resolve_download(self, source_id: str) -> str: ...   # fresh URL if signed/expiring
```

`SearchPage` carries `candidates: list[CandidateVideo]` + opaque `next_cursor`. Adapters must be pure metadata at this stage — no downloads during `search()`.

### 3.2 Adapter roster

| Adapter | Endpoint / lib | Auth | Notes |
|---|---|---|---|
| `pexels` | api.pexels.com/videos | `PEXELS_API_KEY` | Refactor existing logic out of `stock_footage_service.py`. License: Pexels license → map to `LicenseRef-Pexels`. |
| `pixabay` | pixabay.com/api/videos | `PIXABAY_API_KEY` | Same refactor. License → `LicenseRef-Pixabay`. |
| `archive_org` | `internetarchive` pkg (`ia search`, `ia metadata`) or `advancedsearch.php` + metadata API | none for search/download | Prefer curated PD collections: `collection:prelinger`, `collection:PrelingerArchives`, `collection:nasa`, `mediatype:movies AND licenseurl:*`. Resolve best file via `--glob='*.mp4'`-equivalent format ranking (h.264 > MPEG4 > MPEG2). Metadata is librarian-grade: query by `subject:`, `creator:`, `collection:` — not vibes. |
| `nasa` | images-api.nasa.gov (`/search?media_type=video`) | `NASA_API_KEY` optional | PD per NASA media guidelines; store guideline URL in `license_raw`. |
| `loc` | loc.gov JSON API (`?fo=json&c=100&sp=N`) | none (rate-limited) | Filter `online_format:film\,video`; check `rights` field per item — many are PD (early actualities, newsreels). |
| `wikimedia_commons` | MediaWiki API `generator=search&gsrsearch=filetype:video` | none | Per-file license via `extmetadata.LicenseShortName`; map to SPDX; keep `Attribution` field. |
| `coverr` | coverr.co API | `COVERR_API_KEY` | Free commercial use; attribution/logo requirement — set `attribution_text` accordingly and surface in render credits (§4). |
| `europeana` | REST API with `REUSABILITY:open` filter | `EUROPEANA_API_KEY` | Rights filter at query time; still re-check per item. |
| `youtube_cc` (optional, phase 3) | YouTube Data API `license=creativeCommon` + yt-dlp | `YOUTUBE_API_KEY` | CC-BY only; highest legal/ToS scrutiny; off by default. |

Registry (`footage/sources/registry.py`) maps name → class, with per-source `enabled` flag from config.

---

## 4. Licensing Policy & Provenance

Hard gate at the FILTER stage — an asset without an allowlisted license is never downloaded.

**Allowlist (config-driven):**

```yaml
license_allowlist:
  - CC0-1.0
  - public-domain
  - CC-BY-3.0
  - CC-BY-4.0
  - CC-BY-SA-4.0        # requires share-alike flag on output; default: excluded
  - LicenseRef-Pexels
  - LicenseRef-Pixabay
  - LicenseRef-Coverr
  - nasa-media-guidelines
```

Rules:

1. Unknown / missing license → reject (log to `ingest_rejections` with reason).
2. `CC-BY*` and Coverr require `attribution_text`; adapter must populate it or reject.
3. Store provenance verbatim: `license_spdx`, `license_raw`, `page_url`, `attribution_text`, full source metadata JSON, download timestamp.
4. **Render credits:** when `assembly_service` composes a video, it collects attributions for every used shot and appends a credits card / description block. This is a hard requirement, not optional — it's what keeps CC-BY and Coverr clips usable.
5. License changes at source are possible; re-verify `license_raw` on a scheduled re-check for assets older than N days (default 90) before reuse in new renders.

---

## 5. Storage Layout & Normalization

Object storage paths:

```
footage/{source}/{source_id}/master.{ext}      # as-downloaded
footage/{source}/{source_id}/full.mp4          # normalized working copy
footage/{source}/{source_id}/proxy.mp4         # 540p analysis/preview proxy
footage/{source}/{source_id}/poster.jpg
footage/{source}/{source_id}/shots/{shot_idx:04d}.jpg   # keyframe per shot
```

Normalization profile (ffmpeg, applied at NORMALIZE):

```
ffmpeg -i master -vf "scale='min(1920,iw)':-2,fps=fps='min(30,source_fps)'" \
  -c:v libx264 -crf 23 -preset medium -pix_fmt yuv420p \
  -movflags +faststart -c:a aac -b:a 128k full.mp4
```

- Cap duration: skip assets > 10 min at FILTER unless `allow_long_form` (archival reels handled by shot-splitting later — still capped).
- Vertical/odd aspect: keep as-is; record `width/height/aspect`; reframing stays the job of `reframe_service.py`.
- `proxy.mp4`: 540p CRF 28, used by ANALYZE and by the admin review UI.

---

## 6. Analysis Stage

Runs on `proxy.mp4`. All outputs land in `footage_shots` (§7).

1. **Shot segmentation** — PySceneDetect (content detector, threshold tuned on a 50-clip validation set; target ≥95% boundary recall on stock b-roll, lower precision acceptable). Each segment = one row in `footage_shots` with `start_s`, `end_s`.
2. **Embeddings** — open-clip `ViT-L-14` (laion2b) on 3 uniformly sampled frames per shot; L2-normalize each, mean-pool, re-normalize → one 768-d vector per shot. Batch on GPU when available; CPU fallback at reduced batch size (config `EMBED_DEVICE`).
3. **Shot classification** (this is what enables montage logic later):
   - `shot_size` ∈ {ECU, CU, MS, MLS, FS, WS, EWS} — heuristic from face/person detector (YOLOv8n or retinaface) subject-area ratio + heuristics for no-person shots.
   - `camera_motion` ∈ {static, pan, tilt, tracking, handheld, zoom} — dense optical flow (Farnebäck) aggregate direction + magnitude over the shot.
   - `motion_intensity` float — mean flow magnitude (editing rhythm signal).
   - `faces_count`, `has_text_overlay` (OCR-lite via easyocr on keyframe), `brightness`, `color_palette` (k-means k=5 on keyframe).
4. **Dedup (two-tier):**
   - Exact/near: pHash on poster + middle keyframe; Hamming ≤ 6 → mark `duplicate_of`.
   - Semantic: cosine ≥ 0.97 against existing embeddings within same source → `duplicate_of`. Cross-source duplicates kept but down-weighted at retrieval.
5. **Optional captioning** (flag `ENABLE_BLIP`): BLIP-2 caption per shot keyframe → `footage_shots.caption`, also embedded (text encoder) into `caption_embedding` for hybrid retrieval.

All models lazy-loaded per worker; `requirements-ml.txt` already exists — add `open-clip-torch`, `scenedetect[opencv]`, `imagehash`, `ultralytics` (or `deepface`), `easyocr` (optional extra).

---

## 7. Database Schema

Postgres (Supabase) with `vector` extension enabled. Alembic migration + Prisma schema both updated (repo uses both — keep them in sync).

```sql
create table footage_assets (
    id uuid primary key default gen_random_uuid(),
    source text not null,
    source_id text not null,
    title text,
    description text,
    tags text[] default '{}',
    subjects text[] default '{}',
    creator text,
    published_at timestamptz,
    duration_s real,
    width int, height int,
    aspect text,
    license_spdx text not null,
    license_raw text,
    attribution_text text,
    page_url text not null,
    storage_prefix text not null,      -- footage/{source}/{source_id}
    status text not null default 'discovered',  -- discovered|filtered_out|downloaded|normalized|analyzed|failed
    duplicate_of uuid references footage_assets(id),
    source_metadata jsonb not null default '{}',
    last_license_check timestamptz,
    created_at timestamptz default now(),
    unique (source, source_id)
);

create table footage_shots (
    id uuid primary key default gen_random_uuid(),
    asset_id uuid not null references footage_assets(id) on delete cascade,
    shot_idx int not null,
    start_s real not null,
    end_s real not null,
    keyframe_path text,
    embedding vector(768),
    caption text,
    caption_embedding vector(768),
    shot_size text,
    camera_motion text,
    motion_intensity real,
    faces_count int default 0,
    has_text_overlay boolean default false,
    brightness real,
    color_palette jsonb,
    unique (asset_id, shot_idx)
);
create index on footage_shots using hnsw (embedding vector_cosine_ops);

create table ingest_jobs (
    id uuid primary key default gen_random_uuid(),
    source text not null,
    query text not null,
    status text not null default 'pending',   -- pending|running|done|failed
    discovered int default 0,
    filtered_out int default 0,
    ingested int default 0,
    error text,
    created_at timestamptz default now(),
    finished_at timestamptz
);

create table ingest_rejections (
    id uuid primary key default gen_random_uuid(),
    source text not null,
    source_id text not null,
    reason text not null,        -- license_unknown|too_long|no_download_format|...
    detail jsonb,
    created_at timestamptz default now()
);
```

---

## 8. Celery Tasks

Registered in `celery_app.py` under queue `footage`:

| Task | Trigger | Behavior |
|---|---|---|
| `footage.discover(source, query, limit)` | beat schedule per niche topic list + manual API | Pages adapter `search()`, upserts `footage_assets(status='discovered')`, license-filters, enqueues `acquire`. Fully idempotent via `(source, source_id)` unique key. |
| `footage.acquire(asset_id)` | chained | `resolve_download()` → stream to `master.*`, set `status='downloaded'`. Retry 3× backoff; rate-limit per source via Celery rate_limit. |
| `footage.normalize(asset_id)` | chained | ffmpeg profile §5 + poster + proxy. Failure → `status='failed'` with error. |
| `footage.analyze(asset_id)` | chained | §6 pipeline → `footage_shots` rows, dedup pass, `status='analyzed'`. |
| `footage.recheck_licenses()` | beat, daily | Re-fetch metadata for assets due for re-check; on license downgrade → `status='filtered_out'` + excluded from retrieval. |

Beat discovery seeds from `niches/` topic configs so the corpus grows toward what channels actually render. Suggested initial queries per adapter: 20–50 niche-aligned terms + 20 archival-flavored subjects (`subject:"city life"`, `subject:"factories"`, …) for `archive_org`.

---

## 9. Configuration

`.env.example` additions:

```
# Footage ingest
FOOTAGE_STORAGE_ROOT=footage
FOOTAGE_QUEUE=footage
FOOTAGE_SOURCES_ENABLED=pexels,pixabay,archive_org,nasa,loc,wikimedia_commons,coverr
PEXELS_API_KEY=
PIXABAY_API_KEY=
NASA_API_KEY=            # optional
COVERR_API_KEY=
EUROPEANA_API_KEY=
ARCHIVE_ORG_ACCESS=      # only if uploading; search/download need none
EMBED_MODEL=ViT-L-14
EMBED_PRETRAINED=laion2b_s32b_b82k
EMBED_DEVICE=auto
ENABLE_BLIP=false
FOOTAGE_MAX_DURATION_S=600
FOOTAGE_LICENSE_RECHECK_DAYS=90
```

---

## 10. Retrieval API (consumed by `assembly_service`)

New module `footage/retrieval.py` + router:

```
POST /footage/search
{
  "text": "empty factory floor at dawn, melancholic",
  "limit": 12,
  "min_duration_s": 2.0,
  "filters": {
    "shot_size": ["WS", "EWS", "MS"],
    "camera_motion": ["static", "pan"],
    "faces_max": 0,
    "sources": null,               // null = all enabled
    "exclude_used_in_video": "<video_uuid>"
  }
}
→ ranked shots: asset_id, shot window (start_s/end_s), scores, license + attribution_text
```

Ranking: cosine(text-embedding, shot.embedding) × source-quality prior × duplicate penalty. Hybrid mode adds `caption_embedding` when BLIP enabled.

**Migration path:** keep `stock_footage_service.py`'s public interface; swap internals to call `/footage/search` first, fall back to live Pexels/Pixabay only when corpus coverage for a query is below threshold (< N shots above similarity floor). Log fallback rate per niche — that metric tracks corpus adequacy over time.

---

## 11. Rollout & Acceptance

**Phase 0 — skeleton (week 1):** schema + migration; `base.py`/`registry.py`; `archive_org`, `nasa`, `pexels`, `pixabay` adapters; discover+acquire tasks; license gate. Acceptance: 1,000 assets ingested from ≥3 sources, 100% with allowlisted licenses and provenance rows.

**Phase 1 — analysis (week 2):** normalize + analyze tasks, shot table, embeddings. Acceptance: ≥90% of normalized assets produce ≥1 shot; embedding sanity test (query "aerial coastline" returns aerial coastlines in top 5 of a labeled 200-shot validation set).

**Phase 2 — retrieval swap (week 3):** `/footage/search`, `stock_footage_service` behind-flag migration, credits/attribution block in renders. Acceptance: fallback-to-live rate < 30% on last 50 real renders; attribution present for 100% of CC-BY/Coverr shots used.

**Phase 3 — breadth (ongoing):** `loc`, `wikimedia_commons`, `coverr`, `europeana`, optional `youtube_cc`; BLIP captions; cross-source dedup tuning.

**Tests:** adapter contract tests with VCR/recorded fixtures (no live API in CI); license-gate unit tests per license class incl. downgrade path; ffmpeg profile golden-file test; dedup precision/recall on a hand-labeled dup set; retrieval ranking regression set (fixed query → expected top-k membership).

---

## 12. Why This Fixes the "Lumière Problem"

The montage failure isn't only pool size — it's that keyword search has no notion of a *shot*. This service makes the shot the unit of retrieval: every candidate carries shot size, camera motion, motion intensity, duration, and faces. That's the minimal metadata substrate a montage engine (shot-size progression, rhythmic cutting on `motion_intensity`, avoiding three consecutive static CUs of smiling faces) needs. Sources widen the vocabulary; this schema teaches the system grammar.
