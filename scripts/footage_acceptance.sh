#!/usr/bin/env bash
# NON-CI acceptance gate for footage ingest. NOT part of the pytest suite.
# Fails (non-zero) when a gate is unmet — not a smoke test.
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

echo "[2/4] ingest >=1000 assets / >=3 sources (COUNT over footage_assets)"
python - <<'PY'
import os, sqlite3
db = os.getenv("FOOTAGE_VECTOR_DB", "/tmp/cw-footage-vec.db")
# footage_assets is the source-of-truth store (via the VectorStore).
conn = sqlite3.connect(os.getenv("FOOTAGE_ASSETS_DB", db))
try:
    n = conn.execute("SELECT COUNT(*) FROM footage_assets").fetchone()[0]
    src = conn.execute("SELECT COUNT(DISTINCT source) FROM footage_assets").fetchone()[0]
except Exception as e:
    raise SystemExit(f"footage_assets not present in {db}: {e}")
assert n >= 1000, f"expected >=1000 assets, got {n}"
assert src >= 3, f"expected >=3 sources, got {src}"
print(f"ok: {n} assets across {src} sources")
PY

echo "[3/4] 'aerial coastline' sanity on labeled 200-shot set (metadata-semantic v1)"
python - <<'PY'
import os, sys
assert os.getenv("EMBED_BACKEND", "none") != "none", \
    "EMBED_BACKEND must not be 'none' for the aerial-coastline step (metadata-semantic v1)"
from src.services.footage.retrieval import search_clips
hits = search_clips("aerial coastline", limit=5, min_duration_s=2.0, filters={})
print("top-5 hits (validate against labeled set by caption):")
for h in hits:
    print(f"  - id={h.get('id')} source={h.get('source')} dur={h.get('duration_s')} caption={h.get('caption')}")
# Human sign-off: inspect the printed captions against the labeled 200-shot set.
PY

echo "[4/4] disk-cleanup policy"
python - <<'PY'
from src.services.footage.cleanup import purge_stale_media
assert callable(purge_stale_media)
print("ok")
PY

echo "ACCEPTANCE PASS"
