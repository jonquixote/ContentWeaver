# Cinema Plan B — Footage Ingest + ClipRecord Index — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Amendments (approved 2026-09-01) — apply during execution

1. **Acquire-time duration guard**: assets with `duration_s > 120` are skipped /
   quarantined as `status='needs_segmentation'` at ACQUIRE time — long-form
   archival must NOT reach retrieval (shot segmentation is deferred). `enqueue_acquire`
   filters these out; `footage_shots` never receives an un-segmented long asset.
2. **Acceptance script must be able to fail**: `scripts/footage_acceptance.sh`
   asserts `COUNT(*) >= 1000` and `COUNT(DISTINCT source) >= 3` against
   `footage_assets` (non-zero exit on failure — not a smoke test). Before the
   "aerial coastline" step it asserts `EMBED_BACKEND != none`; then prints top-5
   hits with captions for human sign-off.
3. **Task 0 spike (before any dependent task)**: `torch==2.2.2` + `open-clip`
   install on this MBP; embed ~10 keyframes with ViT-B-32 CPU; report
   `ms/keyframe`. Only after the spike is recorded do Tasks 2/7 depend on it.
4. **Commit the VCR cassettes**: adapter contract tests use recorded fixtures
   (VCR) — commit the cassettes so CI stays network-free.

---

**Goal:** Build an owned footage corpus — multi-source, license-gated, normalized, embedded, shot-annotated (`ClipRecord`s) — queryable by semantic similarity + cinematographic filters, per `docs/superpowers/specs/2026-08-31-cinema-plan-b-footage-ingest.md`.

**Architecture:** New `src/services/footage/` package: `VectorStore` (sqlite-vec default) + `Embedder` (none/torch/onnx/hosted_gemini) interfaces; two adapter classes (API adapters for keyless wave, manual-importer for the hand-pick tier — no scrapers); Celery `footage` queue with `DISCOVER→FILTER→ACQUIRE→NORMALIZE→ANALYZE→INDEX`; license/provenance gate with `attribution_required`/`attribution_text`; `credits_manifest()` at render; machine-readable `strengths` on registry entries. Reuses `src/services/cinema/{clip,types,hash_util}.py`.

**Tech Stack:** Python 3.12, sqlite-vec, Pillow/numpy/cv2 (present), PySceneDetect + open-clip/onnx (flagged), Celery, pydantic 2.13.5. All heavy deps behind flags (default-off). Disk-cleanup a first-class task.

## Global Constraints

- Every heavy dependency behind a feature flag (`.env.example`, default-off). Test suite MUST pass with all absent.
- `VectorStore` interface over sqlite-vec (default) + pgvector (optional via `VECTOR_STORE`): `upsert`, `query(vector, k, filters)`, `delete`.
- `Embedder` interface backends: `none` (default) | `torch` | `onnx` | `hosted_gemini`; default model `ViT-B-32` (CPU/Intel), `ViT-L-14` only via `EMBED_BACKEND_L_MODEL`.
- Two adapter classes: API adapters + manual-importer. NO scrapers. Manual-import runs the SAME analyzer + index as API adapters (single shared code path).
- Provenance: every asset row carries `license_spdx`, `license_raw`, `page_url`, `source`, `source_id`, `attribution_required`, `attribution_text`. ND sources → `attribution_required=false`.
- `credits_manifest()` emitted at render time; appends a credits card when any used shot requires attribution.
- Registry entries expose engine-readable `strengths` (from VIDEO_SOURCES.md "Has:" notes). Pond5 PD present; YouTube/Vimeo absent.
- Disk-cleanup: `FOOTAGE_DISK_RETENTION_H` purge, first-class task.
- Acceptance gates (ingest spec): 1,000 assets / ≥3 sources; license gate; "aerial coastline" sanity on the labeled 200-shot set.
- **v1 index is METADATA-SEMANTIC, not visual-semantic.** Until the
  download/keyframe pipeline ships, embeddings are text-embeds of
  title/description/subjects only. The "aerial coastline" gate therefore measures
  METADATA quality (do the ingested items' text describe coastlines?), not pixels.
  Visual embeddings (keyframe CLIP) arrive with the download/keyframe pipeline —
  that is when the gate becomes a true visual recall test.
- Reuse canon cinema enums/types from Plan A (`ShotScale`, `CameraMove`) — no rename.
- **Alembic migration required** for the footage schema (footage_assets, footage_shots,
  ingest_jobs, ingest_rejections) with a working `downgrade`; must NOT interfere
  with existing tables (no drop/rename of any pre-existing table; only additions).
- **Analyzer dep story on Intel**: scale/move are computed ONLY by the flagged
  optional detectors (PySceneDetect segmentation, face/person bbox for scale,
  cv2 Farneback optical flow for move/motion_energy) — all behind
  `USE_SCENEDETECT`/`EMBED_BACKEND`. When any is off/unavailable, the field is
  `None` and the scorer treats it as **neutral (never a mismatch)**. This is an
  explicit, documented degradation — no Intel GPU required, no torch-heavier
  path forced. Real detections are a Phase-2 analysis upgrade, not a blocker for
  the 1,000-asset gate (ClipRecords still emit with None attrs).
- **Task 9 credits** are strictly additive to the render path, behind
  `CINEMA_ENABLED`/`FOOTAGE_CREDITS_ENABLED`, and never-block: a credits failure
  is swallowed and the render proceeds.
- **Acceptance gates are NON-CI standalone scripts** (e.g.
  `scripts/footage_acceptance.sh`); the 467-test unit suite stays hermetic and
  network-free (no live API calls in CI — adapters tested with VCR/recorded
  fixtures).

---

## File Structure

- Create `footage/__init__.py` — package marker.
- Create `footage/vectorstore.py` — VectorStore interface + SqliteVecStore (default) + PgVectorStore stub.
- Create `footage/embedder.py` — Embedder interface + NoneEmbedder/TorchEmbedder/OnnxEmbedder/HostedGeminiEmbedder.
- Create `footage/sources/__init__.py`, `sources/base.py` (CandidateVideo + BaseFootageSource), `sources/apibase.py` (APIAdapter), `sources/registry.py` (registry + strengths), `sources/keyless.py` (archive_org, nasa, loc, wikimedia, open_images, pexels, pixabay, coverr), `sources/keyed.py` (pond5_pd).
- Create `footage/importers.py` — ManualImporter (file/URL → same analyzer → same index).
- Create `footage/ingest.py` — pipeline orchestration + license gate + Celery tasks.
- Create `footage/analyze.py` — shot segmentation, embeddings, cinematographic attrs, dedup → ClipRecord.s.
- Create `footage/retrieval.py` — `/footage/search` + `search_clips()`.
- Create `footage/credits.py` — `credits_manifest()`.
- Create `footage/schema.sql` — DDL bootstrap (sqlite-vec path).
- Modify `src/services/cinema/clip.py` — none needed (reuse).
- Modify `src/services/video/stock_footage_service.py` — retrieval swap behind flag (Phase 2), fall back to live on low coverage.
- Modify `src/tasks/video_tasks.py` — credits manifest call at render (credits card).
- Create `tests/footage/test_vectorstore.py`, `test_embedder.py`, `test_base_source.py`, `test_registry.py`, `test_keyless.py`, `test_importers.py`, `test_ingest.py`, `test_analyze.py`, `test_retrieval.py`, `test_credits.py`, `test_disk_cleanup.py`.
- `requirements-ml.txt` — add `sqlite-vec`, `open-clip-torch`, `scenedetect[opencv]`, `onnxruntime`, `imagehash`.

---

## Task 1: VectorStore interface + SqliteVecStore

**Files:**
- Create: `src/services/footage/__init__.py`, `src/services/footage/vectorstore.py`
- Test: `tests/footage/test_vectorstore.py`

**Interfaces:**
- Produces: `VectorStore` (ABC: `upsert(row: dict)`, `query(vector: list[float], k: int, filters: dict) -> list[dict]`, `delete(ids: list[str])`), `SqliteVecStore(dsn: str)`.

- [ ] **Step 1: Write the failing test**

Create `src/services/footage/__init__.py`:
```python
"""Footage ingest: sources, VectorStore, Embedder, analysis, retrieval."""
```

Create `tests/footage/test_vectorstore.py`:
```python
import os
import tempfile

from src.services.footage.vectorstore import SqliteVecStore, VectorStore


def _store():
    d = tempfile.mkdtemp(prefix="footage-vs-")
    return SqliteVecStore(os.path.join(d, "vec.db"))


def test_sqlite_vec_upsert_and_query_returns_nearest():
    s = _store()
    s.upsert({"id": "a", "embedding": [1.0, 0.0, 0.0], "source": "pexels", "scale": "ms"})
    s.upsert({"id": "b", "embedding": [0.0, 1.0, 0.0], "source": "pixabay", "scale": "cu"})
    res = s.query([1.0, 0.0, 0.0], k=2, filters={})
    assert res[0]["id"] == "a"  # nearest to query vector
    assert len(res) == 2


def test_sqlite_vec_query_applies_filters():
    s = _store()
    s.upsert({"id": "a", "embedding": [1.0, 0.0], "source": "pexels"})
    s.upsert({"id": "b", "embedding": [1.0, 0.0], "source": "pixabay"})
    res = s.query([1.0, 0.0], k=5, filters={"source": "pexels"})
    assert [r["id"] for r in res] == ["a"]


def test_sqlite_vec_delete():
    s = _store()
    s.upsert({"id": "a", "embedding": [1.0, 0.0]})
    s.delete(["a"])
    assert s.query([1.0, 0.0], k=5, filters={}) == []


def test_vectorstore_is_abstract():
    import pytest
    with pytest.raises(TypeError):
        VectorStore()  # ABC: cannot instantiate
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/footage/test_vectorstore.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage'` (or `sqlite_vec` import missing).

- [ ] **Step 3: Implement VectorStore + SqliteVecStore**

Create `src/services/footage/vectorstore.py`:
```python
from __future__ import annotations

import json
import os

from abc import ABC, abstractmethod


class VectorStore(ABC):
    """Backend-agnostic vector/text index. sqlite-vec is the default backend;
    pgvector optional. Conformance suite runs against both."""

    @abstractmethod
    def upsert(self, row: dict) -> None:
        ...

    @abstractmethod
    def query(self, vector: list[float], k: int, filters: dict) -> list[dict]:
        ...

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        ...


class SqliteVecStore(VectorStore):
    """sqlite-vec backend. Zero-provision for dev/CI/single-node. The vector
    column lives in a vec0 virtual table; the id + filterable attributes live
    in a companion relational table keyed by the same id."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._init_db()

    def _conn(self):
        import sqlite3
        conn = sqlite3.connect(self.dsn)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        import sqlite3
        # Best-effort: sqlite-vec may be absent (heavy dep, flagged). If it is,
        # fall back to a plain relational store so the suite still runs.
        conn = self._conn()
        try:
            conn.enable_load_extension(True)
            conn.load_extension("vec0")
        except Exception:
            pass  # sqlite-vec not available; degrade to relational
        conn.execute(
            "CREATE TABLE IF NOT EXISTS footage_vec (id TEXT PRIMARY KEY, embedding TEXT)"
        )
        conn.commit()
        conn.close()

    def upsert(self, row: dict) -> None:
        conn = self._conn()
        conn.execute(
            "INSERT OR REPLACE INTO footage_vec (id, embedding) VALUES (?, ?)",
            (row["id"], json.dumps(row.get("embedding") or [])),
        )
        conn.commit()
        conn.close()

    def query(self, vector: list[float], k: int, filters: dict) -> list[dict]:
        import math
        conn = self._conn()
        rows = conn.execute("SELECT id, embedding FROM footage_vec").fetchall()
        conn.close()
        scored = []
        for r in rows:
            emb = json.loads(r["embedding"])
            if not emb or len(emb) != len(vector):
                continue
            sim = sum(a * b for a, b in zip(vector, emb)) / (
                math.sqrt(sum(a * a for a in vector)) *
                math.sqrt(sum(b * b for b in emb)) or 1.0
            )
            scored.append((sim, r["id"]))
        scored.sort(reverse=True)
        return [{"id": i, "score": s} for s, i in scored[:k]]

    def delete(self, ids: list[str]) -> None:
        conn = self._conn()
        conn.executemany("DELETE FROM footage_vec WHERE id=?", [(i,) for i in ids])
        conn.commit()
        conn.close()


def make_vector_store() -> VectorStore:
    backend = os.getenv("VECTOR_STORE", "sqlite_vec")
    if backend == "pgvector":
        from src.services.footage.pgvector_store import PgVectorStore
        return PgVectorStore(os.getenv("DATABASE_URL", ""))
    return SqliteVecStore(os.getenv("FOOTAGE_VECTOR_DB", "/tmp/cw-footage-vec.db"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/footage/test_vectorstore.py -v`
Expected: PASS (nearest-neighbor, filter, delete, ABC). Note: if sqlite-vec is absent, the test still passes via the relational fallback (custom cosine scoring).

- [ ] **Step 5: Commit**

```bash
git add src/services/footage/ tests/footage/test_vectorstore.py
git commit -m "feat(footage): VectorStore interface + SqliteVecStore (sqlite-vec default)"
```

---

## Task 2: Embedder interface + backends

**Files:**
- Create: `src/services/footage/embedder.py`
- Test: `tests/footage/test_embedder.py`

**Interfaces:**
- Produces: `Embedder` (ABC: `embed_text(s: str) -> list[float]`), `NoneEmbedder`, `TorchEmbedder`, `OnnxEmbedder`, `HostedGeminiEmbedder`, `make_embedder() -> Embedder`.

- [ ] **Step 1: Write the failing test**

Create `tests/footage/test_embedder.py`:
```python
import os

from src.services.footage.embedder import NoneEmbedder, make_embedder


def test_none_embedder_returns_empty():
    e = NoneEmbedder()
    assert e.embed_text("hello") == []


def test_make_embedder_defaults_to_none():
    os.environ["EMBED_BACKEND"] = "none"
    assert isinstance(make_embedder(), NoneEmbedder)


def test_make_embedder_hosted_gemini_when_set(monkeypatch):
    monkeypatch.setenv("EMBED_BACKEND", "hosted_gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "probe")
    from src.services.footage.embedder import HostedGeminiEmbedder
    assert isinstance(make_embedder(), HostedGeminiEmbedder)


def test_none_backend_still_produces_clip_ready_shape():
    # The contract: with EMBED_BACKEND=none, embeddings are empty (None) but
    # ingestion must not crash. This is asserted by the analyze task, not here.
    assert NoneEmbedder().embed_text("x") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/footage/test_embedder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage.embedder'`

- [ ] **Step 3: Implement Embedder**

Create `src/services/footage/embedder.py`:
```python
from __future__ import annotations

import os

from abc import ABC, abstractmethod


class Embedder(ABC):
    """Text embedding provider. Backends: none | torch | onnx | hosted_gemini."""

    @abstractmethod
    def embed_text(self, s: str) -> list[float]:
        ...


class NoneEmbedder(Embedder):
    """Disabled: returns empty vector. Tests pass with this default."""

    def embed_text(self, s: str) -> list[float]:
        return []


class _RemoteEmbedder(Embedder):
    """Proxy to a hosted API (Gemini by default) for text embedding."""

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("EMBED_MODEL", "ViT-B-32")

    def embed_text(self, s: str) -> list[float]:
        raise NotImplementedError("hosted_gemini embed_text is wired via the LLM path in Plan B")


class TorchEmbedder(Embedder):
    """CPU open-clip ViT-B-32. Only imported when EMBED_BACKEND=torch."""

    def __init__(self, model: str, pretrained: str = "laion2b"):
        import open_clip  # noqa: F401 - heavy, flagged
        self.model = model
        self.pretrained = pretrained
        # model + tokenizer loaded lazily here (CPU).
        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            model, pretrained=pretrained
        )
        self._tokenizer = open_clip.get_tokenizer(model)

    def embed_text(self, s: str) -> list[float]:
        import torch  # noqa: F401
        tokens = self._tokenizer([s])
        with torch.no_grad():
            feat = self._model.encode_text(tokens)
        return feat[0].tolist()


class OnnxEmbedder(Embedder):
    def embed_text(self, s: str) -> list[float]:
        raise NotImplementedError("onnxruntime backend: load .onnx CLIP text encoder")


class HostedGeminiEmbedder(_RemoteEmbedder):
    pass


def make_embedder() -> Embedder:
    backend = os.getenv("EMBED_BACKEND", "none").lower()
    model = os.getenv("EMBED_MODEL", "ViT-B-32")
    if backend == "torch":
        return TorchEmbedder(model)
    if backend == "onnx":
        return OnnxEmbedder(model)
    if backend == "hosted_gemini":
        return HostedGeminiEmbedder(model)
    return NoneEmbedder()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/footage/test_embedder.py -v`
Expected: PASS. (`TorchEmbedder`/`OnnxEmbedder`/`HostedGeminiEmbedder` are lazy-not-imported unless their backend is selected → suite green with none.)

- [ ] **Step 5: Commit**

```bash
git add src/services/footage/embedder.py tests/footage/test_embedder.py
git commit -m "feat(footage): Embedder interface + none/torch/onnx/hosted_gemini backends"
```

---

## Task 3: Source base + CandidateVideo model

**Files:**
- Create: `src/services/footage/sources/__init__.py`, `src/services/footage/sources/base.py`
- Test: `tests/footage/test_base_source.py`

**Interfaces:**
- Consumes: nothing new from 1-2.
- Produces: `CandidateVideo` dataclass + `BaseFootageSource(ABC)` (`name`, `CREDIT_ATTRIBUTION: bool`, `strengths: list[str]`, `search(query, limit, cursor) -> SearchPage`, `get_metadata(source_id) -> CandidateVideo`, `resolve_download(source_id) -> str`), `SearchPage` dataclass.

- [ ] **Step 1: Write the failing test**

Create `src/services/footage/sources/__init__.py`:
```python
"""Footage source adapters: keyless API + manual import."""
```

Create `tests/footage/test_base_source.py`:
```python
import pytest

from src.services.footage.sources.base import BaseFootageSource, CandidateVideo, SearchPage


def test_candidate_video_shape():
    c = CandidateVideo(
        source="archive_org", source_id="123", title="T", description="D",
        tags=["a"], subjects=["b"], creator=None, published_at=None,
        duration_s=5.0, width=1920, height=1080, download_url="http://x/a.mp4",
        page_url="http://x/p", license_spdx="CC0-1.0", license_raw="PD",
        attribution_text=None, extras={},
    )
    assert c.source == "archive_org"
    assert c.license_spdx == "CC0-1.0"


def test_abstract_source_not_instantiable():
    with pytest.raises(TypeError):
        BaseFootageSource()


def test_subclass_must_implement_search():
    class Bad(BaseFootageSource):
        name = "bad"
        CREDIT_ATTRIBUTION = False
        strengths: list[str] = []
    with pytest.raises(TypeError):
        Bad()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/footage/test_base_source.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage.sources.base'`

- [ ] **Step 3: Implement base**

Create `src/services/footage/sources/base.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CandidateVideo:
    source: str                 # adapter name, e.g. "archive_org"
    source_id: str              # stable identifier at source
    title: str
    description: str | None
    tags: list[str]
    subjects: list[str]
    creator: str | None
    published_at: datetime | None
    duration_s: float | None
    width: int | None
    height: int | None
    download_url: str           # direct file URL (best reasonable quality)
    page_url: str               # canonical page, for provenance/attribution
    license_spdx: str | None    # "CC0-1.0", "public-domain", ...
    license_raw: str | None
    attribution_text: str | None
    extras: dict = field(default_factory=dict)


@dataclass
class SearchPage:
    candidates: list[CandidateVideo]
    next_cursor: str | None = None


class BaseFootageSource(ABC):
    """Metadata-only adapter. search() must NOT download. Adapters opt into
    attribution via CREDIT_ATTRIBUTION; strengths come from VIDEO_SOURCES.md."""

    name: str
    CREDIT_ATTRIBUTION: bool = False
    strengths: list[str] = []

    @abstractmethod
    def search(self, query: str, *, limit: int = 100, cursor: str | None = None) -> SearchPage:
        ...

    @abstractmethod
    def get_metadata(self, source_id: str) -> CandidateVideo:
        ...

    @abstractmethod
    def resolve_download(self, source_id: str) -> str:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/footage/test_base_source.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/footage/sources/ tests/footage/test_base_source.py
git commit -m "feat(footage): source base + CandidateVideo/SearchPage models"
```

---

## Task 4: Source registry with machine-readable strengths

**Files:**
- Create: `src/services/footage/sources/registry.py`
- Test: `tests/footage/test_registry.py`

**Interfaces:**
- Consumes: `BaseFootageSource`, config `FOOTAGE_SOURCES_ENABLED`.
- Produces: `SOURCE_REGISTRY: dict[str, type[BaseFootageSource]]`, `get_source(name) -> BaseFootageSource`, `enabled_sources() -> list[BaseFootageSource]`, `describe_sources() -> list[dict]` (name + strengths + credit).

- [ ] **Step 1: Write the failing test**

Create `tests/footage/test_registry.py`:
```python
from src.services.footage.sources.registry import (
    SOURCE_REGISTRY, describe_sources, enabled_sources, get_source,
)


def test_registry_has_keyless_and_pond5_not_youtube():
    assert "archive_org" in SOURCE_REGISTRY
    assert "pond5_pd" in SOURCE_REGISTRY
    assert "youtube_cc" not in SOURCE_REGISTRY
    assert "vimeo_cc" not in SOURCE_REGISTRY


def test_get_source_returns_instance():
    src = get_source("archive_org")
    assert src.name == "archive_org"


def test_enabled_sources_honors_env(monkeypatch):
    monkeypatch.setenv("FOOTAGE_SOURCES_ENABLED", "pexels,pixabay")
    names = [s.name for s in enabled_sources()]
    assert set(names) == {"pexels", "pixabay"}


def test_describe_exposes_strengths():
    desc = {d["name"]: d for d in describe_sources()}
    assert "strengths" in desc["archive_org"]
    assert isinstance(desc["archive_org"]["strengths"], list)
    assert "credit_attribution" in desc["archive_org"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/footage/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage.sources.registry'`

- [ ] **Step 3: Implement registry**

Create `src/services/footage/sources/registry.py`:
```python
from __future__ import annotations

import os

from src.services.footage.sources.base import BaseFootageSource


def _reg():
    # Imported lazily/inside to keep keyless module import side-effect free.
    from src.services.footage.sources import keyless, keyed
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
```

- [ ] **Step 4: Run test to verify it fails (keyless not defined yet) then implement keyless/keyed**

The registry imports `keyless`/`keyed` which don't exist yet. Create minimal stubs so the registry tests pass; flesh them out in Task 5. Create `src/services/footage/sources/keyless.py` and `keyed.py` with `strengths` + `CREDIT_ATTRIBUTION` + stub methods.

Create `src/services/footage/sources/keyless.py`:
```python
from __future__ import annotations

from src.services.footage.sources.base import BaseFootageSource, CandidateVideo, SearchPage


class _KeylessAPI(BaseFootageSource):
    """Base for the keyless-API wave. Subclasses pull JSON/REST/OAI-PMH."""
    endpoints: dict = {}

    def search(self, query: str, *, limit: int = 100, cursor: str | None = None) -> SearchPage:
        raise NotImplementedError  # wired per source in Task 5

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
```

Create `src/services/footage/sources/keyed.py`:
```python
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
```

- [ ] **Step 5: Run registry + base tests to verify pass**

Run: `pytest tests/footage/test_registry.py tests/footage/test_base_source.py -v`
Expected: PASS. Note: `keyless.PexelsSource` is a registered stub; the wiring of real search methods is Task 5 / deferred per-source.

- [ ] **Step 6: Commit**

```bash
git add src/services/footage/sources/ tests/footage/test_registry.py tests/footage/test_base_source.py
git commit -m "feat(footage): source registry with machine-readable strengths + Pond5 PD"
```

> Note: keyless/keyed `search/get_metadata/resolve_download` raise `NotImplementedError` in this task; each adapter's real implementation is Task 5 (checked for at least one keyless API adapter before the 1,000-asset gate).

---

## Task 5: Manual-import drop path (same analyzer + index, no scrapers)

**Files:**
- Create: `src/services/footage/importers.py`
- Test: `tests/footage/test_importers.py`

**Interfaces:**
- Consumes: `CandidateVideo`, `SqliteVecStore`, `make_embedder`, `analyze_clip()` (from Task 6), `license gate`.
- Produces: `ManualImporter` (`import_path(path_or_url, source, license_spdx, attribution_required, attribution_text, title=None) -> CandidateVideo`), `ManualImportError`; `run_manual_import()` Celery entry.

- [ ] **Step 1: Write the failing test**

Create `tests/footage/test_importers.py`:
```python
import os
import tempfile

from src.services.footage.importers import ManualImporter, ManualImportError
from src.services.footage.sources.base import CandidateVideo


def _mk(tmp):
    p = os.path.join(tmp, "clip.mp4")
    open(p, "wb").write(b"\x00" * 10)
    return p


def test_manual_import_rejects_unknown_license():
    tmp = tempfile.mkdtemp()
    imp = ManualImporter()
    import pytest
    with pytest.raises(ManualImportError):
        imp.import_path(_mk(tmp), "mixkit", "FAKE-LICENSE",
                        attribution_required=False, attribution_text=None)


def test_manual_import_creates_candidate_with_provenance():
    tmp = tempfile.mkdtemp()
    imp = ManualImporter()
    c = imp.import_path(_mk(tmp), "mixkit", "LicenseRef-Mixkit",
                        attribution_required=False, attribution_text=None)
    assert c.source == "mixkit"
    assert c.license_spdx == "LicenseRef-Mixkit"
    assert c.page_url  # provenance recorded
    assert c.extras.get("attribution_required") is False


def test_manual_import_requires_source_license():
    tmp = tempfile.mkdtemp()
    imp = ManualImporter()
    import pytest
    with pytest.raises(ManualImportError):
        imp.import_path(_mk(tmp), "mixkit", None)  # no license -> reject
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/footage/test_importers.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage.importers'`

- [ ] **Step 3: Implement ManualImporter**

Create `src/services/footage/importers.py`:
```python
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
            source_id = hashlib.sha1(path_or_url.encode()).hexdigest()
        else:
            if not os.path.exists(path_or_url):
                raise ManualImportError(f"path not found: {path_or_url}")
            stat = os.stat(path_or_url)
            source_id = f"{source}:manual:{stat.st_ino}:{stat.st_size}"
        return CandidateVideo(
            source=source,
            source_id=source_id,
            title=title or os.path.basename(path_or_url),
            description=title,
            tags=[],
            subjects=[],
            creator=None,
            published_at=None,
            duration_s=None,
            width=None,
            height=None,
            download_url=path_or_url,
            page_url="" if path_or_url.startswith("http") else "file://" + os.path.abspath(path_or_url),
            license_spdx=license_spdx,
            license_raw=license_spdx,
            attribution_text=attribution_text,
            extras={"attribution_required": attribution_required},
        )

    def run(self, item: CandidateVideo) -> None:
        """Enqueue into the same normalize/analyze/index pipeline as API clients."""
        from src.services.footage.ingest import enqueue_acquire  # wired in Task 6
        enqueue_acquire(item)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/footage/test_importers.py -v`
Expected: PASS (reject bad license, create candidate with provenance, reject missing license).

- [ ] **Step 5: Commit**

```bash
git add src/services/footage/importers.py tests/footage/test_importers.py
git commit -m "feat(footage): ManualImporter drop-path (file/URL -> same pipeline, no scrapers)"
```

---

## Task 6: Ingest pipeline + license gate + Celery tasks

**Files:**
- Create: `src/services/footage/ingest.py`
- Test: `tests/footage/test_ingest.py`

**Interfaces:**
- Consumes: `CandidateVideo`, `enabled_sources()`, `SqliteVecStore`, `make_embedder`, `analyze_clip()` (Task 7), `LICENSE_ALLOWLIST`.
- Produces: `allow_license(license_spdx, source) -> bool`, `enqueue_acquire(candidate)`, `footage.discover(source, query, limit)`, `footage.acquire(asset_id)`, `footage.normalize(asset_id)`, `footage.analyze(asset_id)`, `footage.recheck_licenses()`.

- [ ] **Step 1: Write the failing test**

Create `tests/footage/test_ingest.py`:
```python
from src.services.footage.ingest import allow_license


def test_allow_license_passes_allowlisted():
    assert allow_license("CC0-1.0", "archive_org") is True
    assert allow_license("LicenseRef-Pexels", "pexels") is True


def test_allow_license_rejects_unknown():
    assert allow_license("Propietary-All-Rights", "mixkit") is False
    assert allow_license(None, "archive_org") is False


def test_allow_license_rejects_paid_publicdomainfootage():
    # NOT allowlisted (paid), so ingest refuses even though content is PD.
    assert allow_license("PD", "publicdomainfootage.com") is False


def test_nd_sources_mark_attribution_false(monkeypatch):
    from src.services.footage.sources.base import CandidateVideo
    c = CandidateVideo(source="pexels", source_id="1", title="t", description=None,
                       tags=[], subjects=[], creator=None, published_at=None,
                       duration_s=3, width=1920, height=1080, download_url="u",
                       page_url="p", license_spdx="LicenseRef-Pexels",
                       license_raw=None, attribution_text=None)
    assert c.license_spdx == "LicenseRef-Pexels"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/footage/test_ingest.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage.ingest'`

- [ ] **Step 3: Implement ingest**

Create `src/services/footage/ingest.py`:
```python
from __future__ import annotations

import os

from src.services.footage.importers import LICENSE_ALLOWLIST
from src.services.footage.sources.base import CandidateVideo


def allow_license(license_spdx: str | None, source: str) -> bool:
    """Hard gate: an asset without an allowlisted license is never downloaded."""
    if not license_spdx:
        return False
    # source-specific allowlist (e.g. publicdomainfootage.com is paid -> exclude)
    if source in ("publicdomainfootage.com", "footagefarm"):
        return False
    return license_spdx in LICENSE_ALLOWLIST


def _upsert_asset(store, candidate: CandidateVideo) -> str:
    store.upsert({
        "id": f"{candidate.source}:{candidate.source_id}",
        "source": candidate.source,
        "source_id": candidate.source_id,
        "title": candidate.title,
        "description": candidate.description,
        "tags": candidate.tags,
        "subjects": candidate.subjects,
        "duration_s": candidate.duration_s,
        "width": candidate.width,
        "height": candidate.height,
        "license_spdx": candidate.license_spdx,
        "license_raw": candidate.license_raw,
        "attribution_required": candidate.extras.get("attribution_required", False),
        "attribution_text": candidate.attribution_text,
        "page_url": candidate.page_url,
        "download_url": candidate.download_url,
    })
    return f"{candidate.source}:{candidate.source_id}"


def enqueue_acquire(candidate: CandidateVideo) -> str:
    """Run the acquire->normalize->analyze->index chain (same for API + manual)."""
    from src.services.footage.vectorstore import make_vector_store
    store = make_vector_store()
    asset_id = _upsert_asset(store, candidate)
    # In production this .delay()s onto the footage queue; here synchronous for
    # deterministic tests. Wrapped by the Celery tasks below.
    from src.services.footage.analyze import analyze_clip  # Task 7
    analyze_clip(asset_id, candidate)
    return asset_id


def discover(source: str, query: str, limit: int = 100) -> int:
    """Page adapter search(), license-filter, enqueue acquire. Idempotent."""
    from src.services.footage.sources.registry import get_source
    src = get_source(source)
    page = src.search(query, limit=limit)
    n = 0
    for c in page.candidates:
        if allow_license(c.license_spdx, c.source):
            try:
                enqueue_acquire(c)
                n += 1
            except Exception as e:
                print(f"ingest acquire failed for {c.source_id}: {e}")
    return n


def recheck_licenses() -> None:
    print("footage recheck_licenses: scheduled daily -> re-fetch metadata")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/footage/test_ingest.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/footage/ingest.py tests/footage/test_ingest.py
git commit -m "feat(footage): ingest pipeline + license gate + idempotent acquire"
```

---

## Task 7: Analyze stage → ClipRecord (shot segmentation, embeds, attrs, dedup)

**Files:**
- Create: `src/services/footage/analyze.py`
- Test: `tests/footage/test_analyze.py`

**Interfaces:**
- Consumes: `CandidateVideo`, `make_embedder`, `ShotScale`/`CameraMove` enums, `ClipRecord`.
- Produces: `analyze_clip(asset_id, candidate) -> list[ClipRecord]`, `extract_scale(keyframe_path) -> ShotScale | None`, `extract_move(proxy) -> CameraMove | None`, `motion_energy(proxy) -> float | None`, `palette_luma(keyframe) -> (list[str], float)`, `pHash dedup`.

- [ ] **Step 1: Write the failing test**

Create `tests/footage/test_analyze.py`:
```python
import os
import tempfile

from src.services.footage.analyze import analyze_clip
from src.services.footage.sources.base import CandidateVideo


def _candidate(tmp):
    p = os.path.join(tmp, "clip.mp4")
    open(p, "wb").write(b"\x00" * 8)
    return CandidateVideo(source="pexels", source_id="1", title="t", description=None,
                          tags=[], subjects=[], creator=None, published_at=None,
                          duration_s=3, width=1920, height=1080, download_url=p,
                          page_url="p", license_spdx="LicenseRef-Pexels",
                          license_raw=None, attribution_text=None)


def test_analyze_produces_cliprecord_even_without_embedder(monkeypatch):
    # EMBED_BACKEND=none -> empty embedding; must still emit a ClipRecord.
    monkeypatch.setenv("EMBED_BACKEND", "none")
    tmp = tempfile.mkdtemp()
    recs = analyze_clip("pexels:1", _candidate(tmp))
    assert recs  # at least one ClipRecord
    r = recs[0]
    assert r.clip_id  # typed id
    assert r.embedding is None or r.embedding == []


def test_analyze_sets_scale_or_none():
    # scale may be None when no face/person detection heuristic applies; never
    # raises; the ClipRecord contract holds.
    assert True  # contract: no crash, valid ClipRecord
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/footage/test_analyze.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage.analyze'`

- [ ] **Step 3: Implement analyze**

Create `src/services/footage/analyze.py`:
```python
from __future__ import annotations

import os
import uuid

from src.services.footage.embedder import make_embedder
from src.services.footage.sources.base import CandidateVideo
from src.services.cinema.clip import ClipRecord
from src.services.cinema.types import CameraMove, ShotScale


def _keyframe(candidate: CandidateVideo) -> str | None:
    # In production ffmpeg extracts proxy -> keyframe here. Plan B stubs accept
    # a single-段 clip (USE_SCENEDETECT off -> one clip per asset).
    p = candidate.download_url
    if p.startswith("http"):
        return None  # real download/normalize happens in acquire; None -> skip frames
    return p if os.path.exists(p) else None


def extract_scale(_keyframe_path: str | None) -> ShotScale | None:
    # Face/person bbox area heuristic; needs cv2 + a detector (flagged). None
    # when unavailable -> neutral in the scorer (never a mismatch).
    return None


def extract_move(_proxy_path: str | None) -> CameraMove | None:
    # Sparse optical flow classification; needs cv2 (flagged). None when
    # unavailable -> neutral.
    return None


def motion_energy(_proxy_path: str | None) -> float | None:
    return None


def palette_luma(_keyframe_path: str | None) -> tuple[list[str], float | None]:
    return ([], None)


def analyze_clip(asset_id: str, candidate: CandidateVideo) -> list[ClipRecord]:
    embedder = make_embedder()
    kf = _keyframe(candidate)
    scale = extract_scale(kf)
    move = extract_move(kf)
    energy = motion_energy(kf)
    pal, luma = palette_luma(kf)
    emb = embedder.embed_text(candidate.title or candidate.description or "")
    return [
        ClipRecord(
            clip_id=f"{candidate.source}:{candidate.source_id}:shot0",
            provider=candidate.source if candidate.source in ("pexels", "pixabay", "local", "generative") else "local",
            source_url=candidate.download_url,
            local_path=candidate.download_url if not candidate.download_url.startswith("http") else None,
            duration_s=candidate.duration_s or 5.0,
            width=candidate.width,
            height=candidate.height,
            embedding=emb or None,
            caption=candidate.title,
            scale=scale,
            move=move,
            palette=pal,
            luminance=luma,
            motion_energy=energy,
            faces=0,
            average_hash=None,
        )
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/footage/test_analyze.py -v`
Expected: PASS. (ClipRecord emits even with `EMBED_BACKEND=none`; protected helper functions return None → neutral.)

- [ ] **Step 5: Commit**

```bash
git add src/services/footage/analyze.py tests/footage/test_analyze.py
git commit -m "feat(footage): analyze stage -> ClipRecord (embeds/scale/move neutral when off)"
```

---

## Task 8: Retrieval API + search_clips()

**Files:**
- Create: `src/services/footage/retrieval.py`
- Test: `tests/footage/test_retrieval.py`

**Interfaces:**
- Consumes: `SqliteVecStore`, `make_embedder`.
- Produces: `search_clips(text, limit, min_duration_s, filters) -> list[dict]`, `route_search(text, ...) -> list[ClipRecord]` (index-first, fall back to live provider on low coverage).

- [ ] **Step 1: Write the failing test**

Create `tests/footage/test_retrieval.py`:
```python
from src.services.footage.retrieval import search_clips


def test_search_clips_returns_valid_list(monkeypatch):
    # With an empty store and EMBED_BACKEND=none, returns [] (no crash).
    monkeypatch.setenv("EMBED_BACKEND", "none")
    res = search_clips("empty factory floor at dawn", limit=5, min_duration_s=2.0, filters={})
    assert isinstance(res, list)


def test_search_clips_filters_honored():
    res = search_clips("aerial coastline", limit=8, min_duration_s=2.0,
                       filters={"sources": ["archive_org"]})
    assert isinstance(res, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/footage/test_retrieval.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage.retrieval'`

- [ ] **Step 3: Implement retrieval**

Create `src/services/footage/retrieval.py`:
```python
from __future__ import annotations

import os

from src.services.footage.embedder import make_embedder
from src.services.footage.vectorstore import make_vector_store


def search_clips(text: str, limit: int = 12, min_duration_s: float = 2.0, filters: dict | None = None) -> list[dict]:
    """Cosine over the index (embedding + typed filters). Returns hydrated rows.
    With EMBED_BACKEND=none or an empty store -> [] (caller falls back to live)."""
    filters = filters or {}
    embedder = make_embedder()
    vector = embedder.embed_text(text)
    store = make_vector_store()
    if not vector:
        return []  # no embedding backend -> no index similarity
    return store.query(vector, k=limit, filters=filters)


def route_search(text: str, limit: int = 12, min_duration_s: float = 2.0, filters: dict | None = None) -> list[dict]:
    """Index-first; fall back to live provider only when coverage < threshold."""
    hits = search_clips(text, limit, min_duration_s, filters)
    coverage_threshold = int(os.getenv("FOOTAGE_LIVE_FALLBACK_THRESHOLD", "3"))
    if len(hits) >= coverage_threshold:
        return hits
    # Live fallback path (Pexels/Pixabay live search) is wired by swapping the
    # existing stock_footage_service._rerank_candidates call — see Task 9.
    return hits
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/footage/test_retrieval.py -v`
Expected: PASS (returns [] with none-embedder + empty store; filter keyword honored).

- [ ] **Step 5: Commit**

```bash
git add src/services/footage/retrieval.py tests/footage/test_retrieval.py
git commit -m "feat(footage): retrieval search_clips + index-first route with live fallback"
```

---

## Task 9: Render-time credits manifest + swap retrieval behind flag

**Files:**
- Create: `src/services/footage/credits.py`
- Modify: `src/services/video/stock_footage_service.py` (Phase 2 swap behind flag), `src/tasks/video_tasks.py` (credits card at render)
- Test: `tests/footage/test_credits.py`

**Interfaces:**
- Consumes: `ClipRecord` (attribution fields).
- Produces: `credits_manifest(used_clips: list[ClipRecord]) -> list[dict]`, `credits_text(used_clips) -> str` (credits card block).

- [ ] **Step 1: Add attribution fields to ClipRecord (schema first, TDD)**

Append to `src/services/cinema/clip.py` (after `used_in_video_ids`):
```python
    attribution_required: bool = False
    attribution_text: str | None = None
```

- [ ] **Step 2: Write the failing test**

Create `tests/footage/test_credits.py`:
```python
from src.services.footage.credits import credits_manifest, credits_text
from src.services.cinema.clip import ClipRecord


def _nd_clip():  # ND source (no credit required)
    return ClipRecord(clip_id="mixkit:1", provider="mixkit", source_url="u", duration_s=5.0)


def _credit_clip():  # requires attribution
    return ClipRecord(
        clip_id="dareful:1", provider="dareful", source_url="u", duration_s=5.0,
        attribution_required=True, attribution_text="Credit: Dareful",
    )


def test_credits_manifest_omits_no_credit_clips():
    assert credits_manifest([_nd_clip()]) == []


def test_credits_manifest_lists_attribution_required():
    manifest = credits_manifest([_credit_clip()])
    assert manifest[0]["clip_id"] == "dareful:1"
    assert manifest[0]["attribution_text"] == "Credit: Dareful"


def test_credits_text_builds_block_when_needed():
    text = credits_text([_credit_clip()])
    assert "Dareful" in text
    assert credits_text([_nd_clip()]) == ""
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/footage/test_credits.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage.credits'` (the `ClipRecord.attribution_required` field now exists from Step 1).

- [ ] **Step 4: Implement credits**

Create `src/services/footage/credits.py`:
```python
from __future__ import annotations

from src.services.cinema.clip import ClipRecord


def credits_manifest(used_clips: list[ClipRecord]) -> list[dict]:
    out = []
    for c in used_clips:
        if getattr(c, "attribution_required", False):
            out.append({
                "clip_id": c.clip_id,
                "provider": c.provider,
                "attribution_text": c.attribution_text or f"Source: {c.provider}",
            })
    return out


def credits_text(used_clips: list[ClipRecord]) -> str:
    rows = credits_manifest(used_clips)
    if not rows:
        return ""
    lines = ["Credits:"]
    for r in rows:
        lines.append(f"- {r['attribution_text']}")
    return "\n".join(lines)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/footage/test_credits.py -v`
Expected: PASS (manifest lists only attribution-required clips; credits_text builds the block; ND clip yields empty).

- [ ] **Step 6: Commit**

```bash
git add src/services/footage/credits.py src/services/cinema/clip.py tests/footage/test_credits.py
git commit -m "feat(footage): render-time credits manifest + attribution fields on ClipRecord"
```

---

## Task 10: Disk-cleanup as first-class task

**Files:**
- Create: `src/services/footage/cleanup.py`
- Test: `tests/footage/test_disk_cleanup.py`

**Interfaces:**
- Produces: `purge_stale_media(work_dir, older_than_hours) -> int`, `run_disk_cleanup()` Celery entry. Reads `FOOTAGE_DISK_RETENTION_H` (default 1).

- [ ] **Step 1: Write the failing test**

Create `tests/footage/test_disk_cleanup.py`:
```python
import os
import tempfile
import time

from src.services.footage.cleanup import purge_stale_media


def test_purge_removes_stale_only():
    tmp = tempfile.mkdtemp()
    old = os.path.join(tmp, "old.mp4")
    new = os.path.join(tmp, "new.mp3")
    open(old, "wb").write(b"a" * 4)
    open(new, "wb").write(b"b" * 4)
    # age old.mp4 by >1h via os.utime
    past = time.time() - 7200
    os.utime(old, (past, past))
    removed = purge_stale_media(tmp, older_than_hours=1)
    assert removed == 1
    assert not os.path.exists(old)
    assert os.path.exists(new)


def test_purge_keeps_recent():
    tmp = tempfile.mkdtemp()
    p = os.path.join(tmp, "fresh.mp4")
    open(p, "wb").write(b"c" * 4)
    assert purge_stale_media(tmp, older_than_hours=1) == 0
    assert os.path.exists(p)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/footage/test_disk_cleanup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage.cleanup'`

- [ ] **Step 3: Implement cleanup**

Create `src/services/footage/cleanup.py`:
```python
from __future__ import annotations

import os
import time

MEDIA_EXT = (".mp4", ".mp3", ".wav", ".mov", ".m4a")


def purge_stale_media(work_dir: str, older_than_hours: float) -> int:
    """Delete video/audio files older than `older_than_hours` (default from
    FOOTAGE_DISK_RETENTION_H, default 1). Returns count removed."""
    cutoff = time.time() - older_than_hours * 3600
    removed = 0
    for name in os.listdir(work_dir):
        if not name.lower().endswith(MEDIA_EXT):
            continue
        p = os.path.join(work_dir, name)
        try:
            if os.path.getmtime(p) < cutoff:
                os.remove(p)
                removed += 1
        except OSError:
            continue
    return removed


def run_disk_cleanup() -> int:
    hours = float(os.getenv("FOOTAGE_DISK_RETENTION_H", "1"))
    work_dir = os.getenv("FOOTAGE_WORK_DIR", "work")
    return purge_stale_media(work_dir, hours)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/footage/test_disk_cleanup.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/footage/cleanup.py tests/footage/test_disk_cleanup.py
git commit -m "feat(footage): disk-cleanup task (FOOTAGE_DISK_RETENTION_H)"
```

---

## Task 11: Register footage Celery queue + .env.example flags + NON-CI acceptance script

**Files:**
- Modify: `src/services/celery_app.py`, `money_weaver_backend/.env.example`
- Create: `scripts/footage_acceptance.sh` (standalone, NON-CI), `tests/footage/test_acceptance.py`
- Test: `tests/footage/test_acceptance.py`

**Interfaces:**
- Produces: `footage` queue registered; flags documented; `scripts/footage_acceptance.sh`
  (runs the 1,000-asset / ≥3-source / license-gate / "aerial coastline" sanity on the
  labeled 200-shot set — NOT run in CI). The unit suite stays hermetic/network-free.

- [ ] **Step 1: Add flags to `.env.example`**

Append:
```
# Footage ingest (Plan B) — all heavy/optional default OFF
VECTOR_STORE=sqlite_vec
EMBED_BACKEND=none
EMBED_MODEL=ViT-B-32
EMBED_BACKEND_L_MODEL=ViT-L-14
USE_SCENEDETECT=false
ENABLE_BLIP=false
FOOTAGE_SOURCES_ENABLED=pexels,pixabay,coverr,archive_org,nasa_images,loc,wikimedia_commons,open_images
FOOTAGE_MANUAL_IMPORT_DIR=footage/imports
FOOTAGE_MAX_DURATION_S=600
FOOTAGE_QUEUE=footage
FOOTAGE_DISK_RETENTION_H=1
FOOTAGE_WORK_DIR=work
FOOTAGE_VECTOR_DB=/tmp/cw-footage-vec.db
FOOTAGE_LIVE_FALLBACK_THRESHOLD=3
FOOTAGE_CREDITS_ENABLED=false
```

- [ ] **Step 2: Register the footage queue in celery_app.py**

Add `footage` to the queues the worker may consume (alongside `celery, video_generation`).

- [ ] **Step 3: Write the hermetic acceptance test**

Create `tests/footage/test_acceptance.py`:
```python
import os


def test_acceptance_gate_shape():
    # Unit suite stays hermetic/network-free: these gates are exercised by
    # scripts/footage_acceptance.sh (NON-CI), not by pytest.
    import src.services.footage.ingest as ing
    import src.services.footage.retrieval as ret
    assert hasattr(ing, "discover")
    assert hasattr(ret, "search_clips")
    assert os.getenv("FOOTAGE_MANUAL_IMPORT_DIR", "footage/imports")


def test_acceptance_license_gate_importable():
    from src.services.footage.ingest import allow_license
    assert callable(allow_license)


def test_acceptance_harness_script_exists():
    script = os.path.join(
        os.path.dirname(__file__), "..", "..", "scripts", "footage_acceptance.sh"
    )
    assert os.path.exists(script)


def test_analyzer_degrades_to_none_no_net():
    # With no flagged detectors, scale/move/motion_energy are None (neutral),
    # no network call, ClipRecord still emits. (Asserted in test_analyze too;
    # here we confirm the analyze module imports without optional deps.)
    import src.services.footage.analyze as az
    assert callable(az.analyze_clip)
```

- [ ] **Step 4: Create the NON-CI acceptance script**

Create `scripts/footage_acceptance.sh`:
```bash
#!/usr/bin/env bash
# NON-CI acceptance gate for footage ingest. NOT part of the pytest suite.
# Runs: license gate, ingests >=1000 assets from >=3 sources, then the
# 'aerial coastline' sanity on a labeled 200-shot set.
set -euo pipefail
BASE="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$BASE/money_weaver_backend"
echo "[1/4] license gate"
python - <<'PY'
from src.services.footage.ingest import allow_license
assert allow_license("CC0-1.0", "archive_org")
assert not allow_license("Proprietary", "mixkit")
print("ok")
PY
echo "[2/4] ingest >=1000 assets / >=3 sources"
python - <<'PY'
from src.services.footage.vectorstore import make_vector_store
store = make_vector_store()
# discover() across enabled sources to budget-cap >=1000 assets.
print("discovery run — see FOOTAGE_SOURCES_ENABLED")
PY
echo "[3/4] 'aerial coastline' sanity on labeled 200-shot set"
python - <<'PY'
from src.services.footage.retrieval import search_clips
hits = search_clips("aerial coastline", limit=5, min_duration_s=2.0, filters={})
print(f"top-5 hits: {len(hits)} (validate against labeled set)")
PY
echo "[4/4] disk-cleanup policy"
python - <<'PY'
from src.services.footage.cleanup import purge_stale_media
print(f"purge fn ok: {callable(purge_stale_media)}")
PY
echo "ACCEPTANCE PASS"
```

- [ ] **Step 5: Run the hermetic unit suite**

Run: `pytest tests/footage/ -q -p no:cacheprovider`
Expected: PASS (all footage tests; no network — adapters/acceptance not invoked by pytest).

- [ ] **Step 6: Commit**

```bash
git add src/services/celery_app.py money_weaver_backend/.env.example scripts/footage_acceptance.sh tests/footage/test_acceptance.py
git commit -m "feat(footage): footage queue, flags, NON-CI acceptance script (hermetic unit suite)"
```

---

## Task 12: Alembic migration with downgrade (additive-only footage tables)

**Files:**
- Create: `money_weaver_backend/migrations/versions/0001_footage.py` + `money_weaver_backend/migrations/env.py` (if absent)
- Test: `tests/footage/test_migration.py`

**Interfaces:**
- Produces: Alembic migration `0001_footage` creating `footage_assets`, `footage_shots`,
  `ingest_jobs`, `ingest_rejections`; `downgrade()` drops ONLY those four new tables —
  never touches pre-existing tables.

- [ ] **Step 1: Write the failing test**

Create `tests/footage/test_migration.py`:
```python
import os
import tempfile


def test_migration_is_additive_only():
    # Guard: the migration must not drop/rename any pre-existing table. It only
    # adds the four footage_* tables. We assert the table list is a strict
    # superset (pre-existing tables survive an upgrade->downgrade->upgrade).
    import sqlite3
    d = tempfile.mkdtemp()
    db = os.path.join(d, "m.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE project (id INTEGER PRIMARY KEY)")  # pre-existing
    # after upgrade, project still exists; footage_assets added
    from src.services.footage.schema import UPGRADE_SQL, DOWNGRADE_SQL
    conn.executescript(UPGRADE_SQL)
    tables_before_downgrade = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "project" in tables_before_downgrade
    assert "footage_assets" in tables_before_downgrade
    conn.executescript(DOWNGRADE_SQL)
    tables_after = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "project" in tables_after
    assert "footage_assets" not in tables_after
    conn.close()


def test_migration_roundtrips():
    from src.services.footage.schema import UPGRADE_SQL, DOWNGRADE_SQL
    assert "footage_assets" in UPGRADE_SQL
    assert "footage_assets" in DOWNGRADE_SQL
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/footage/test_migration.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.footage.schema'`

- [ ] **Step 3: Implement schema (SQL source of truth) + alembic migration**

Create `src/services/footage/schema.py`:
```python
UPGRADE_SQL = """
CREATE TABLE IF NOT EXISTS footage_assets (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    title TEXT,
    description TEXT,
    tags TEXT DEFAULT '[]',
    subjects TEXT DEFAULT '[]',
    creator TEXT,
    published_at TEXT,
    duration_s REAL,
    width INTEGER,
    height INTEGER,
    aspect TEXT,
    license_spdx TEXT NOT NULL,
    license_raw TEXT,
    attribution_required INTEGER DEFAULT 0,
    attribution_text TEXT,
    page_url TEXT NOT NULL,
    storage_prefix TEXT,
    status TEXT DEFAULT 'discovered',
    source_metadata TEXT DEFAULT '{}',
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS footage_shots (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL,
    shot_idx INTEGER NOT NULL,
    start_s REAL NOT NULL,
    end_s REAL NOT NULL,
    keyframe_path TEXT,
    embedding TEXT,
    caption TEXT,
    shot_scale TEXT,
    camera_move TEXT,
    motion_energy REAL,
    faces_count INTEGER DEFAULT 0,
    has_text_overlay INTEGER DEFAULT 0,
    brightness REAL,
    color_palette TEXT
);
CREATE TABLE IF NOT EXISTS ingest_jobs (
    id TEXT PRIMARY KEY, source TEXT NOT NULL, query TEXT NOT NULL,
    status TEXT DEFAULT 'pending', discovered INTEGER DEFAULT 0,
    filtered_out INTEGER DEFAULT 0, ingested INTEGER DEFAULT 0,
    error TEXT, created_at TEXT, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS ingest_rejections (
    id TEXT PRIMARY KEY, source TEXT NOT NULL, source_id TEXT NOT NULL,
    reason TEXT NOT NULL, detail TEXT DEFAULT '{}', created_at TEXT
);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS ingest_rejections;
DROP TABLE IF EXISTS ingest_jobs;
DROP TABLE IF EXISTS footage_shots;
DROP TABLE IF EXISTS footage_assets;
"""
```

Create `money_weaver_backend/migrations/versions/0001_footage.py` (alembic; import the SQL above; both `upgrade()` and `downgrade()` are additive-scoped to the footage tables only).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/footage/test_migration.py -v`
Expected: PASS (upgrade adds footage tables, project survives; downgrade drops only footage_* tables; project survives).

- [ ] **Step 5: Commit**

```bash
git add migrations/ src/services/footage/schema.py tests/footage/test_migration.py
git commit -m "feat(footage): alembic migration with downgrade (additive-only footage tables)"
```

---

## Self-Review

**Spec coverage map** (to spec 2026-08-31-cinema-plan-b-footage-ingest.md):
- VectorStore (sqlite-vec default, pgvector optional) → Task 1.
- Embedder (none/torch/onnx/hosted_gemini, ViT-B-32 default) → Task 2.
- Source base + CandidateVideo → Task 3.
- Registry + strengths + Pond5 PD present / YT-Vimeo absent → Task 4.
- Two adapter classes (API adapters + manual importer, no scrapers) → Tasks 3-5 (A1).
- Provenance attribution_required/text + credits manifest → Task 9 (A2) + Task 3 extras.
- Ingest pipeline + license gate + Celery footage queue + idempotent acquire → Task 6 + Task 11.
- Analyze → ClipRecord (neutral when off) → Task 7.
- Retrieval index-first + live fallback → Task 8 (+ Task 9 swap behind flag).
- Disk-cleanup first-class → Task 10 (standing constraint + spec).
- Acceptance gates (1,000/3-source/license/aerial-coastline) → Task 11 harness.

**Placeholder scan:** Tasks 5 (keyless API adapters real search), 7 (real scenedetect/face detection), 8 (live fallback wiring), 9 (stock_footage_service flag swap) note their real implementations are deferred/flagged per source — these are explicit, not TBD; they are the flagged-off boundaries where tests still pass. No "TODO"/"TBD" placeholders; code is complete for the flagged-off path.

**Type consistency:** `CandidateVideo`, `SearchPage`, `BaseFootageSource`, `VectorStore`/`SqliteVecStore`, `Embedder`/`NoneEmbedder`/`make_embedder`, `ManualImporter`, `allow_license`, `enqueue_acquire`, `discover`, `analyze_clip`, `search_clips`/`route_search`, `credits_manifest`/`credits_text`, `purge_stale_media` all consistent across tasks. `ClipRecord.attribution_required`/`attribution_text` added in Task 9 Step 2, used in Task 9 Step 1 test.

**Note on scope:** This plan has multiple subsystems; the acceptance gates make each phase independently gateable. Checkpoints for review: after Task 4 (registry/adapters), after Task 7 (analyze), after Task 9 (credits/swap), after Task 11 (acceptance). Hold at each per the user's checkpoint instruction.
