# Cinema Engine — follow-ups (2026-09-01)

## Plan A
- **Direct doubling of `director_source` in eyeball run**: `get_stock_videos_for_script`
  appears to run twice during one render (two scene passes with slightly different
  rerank counts; downloads log once). Likely a duplicate worker execution
  (worker warm-shutdown/restart mid-run at 01:04), NOT the cache — the
  deterministic path writes no cache. Verify with a clean single-worker
  instrumented re-run; add a task-level idempotency guard if confirmed.
- Clamp / standardize cache writes for director so a cached scene is unambiguous.

## Disk / infra
- Integrate disk-cleanup as a first-class task: purge work/ video+audio older
  than 1h before/after renders (ad-hoc done; needs a scheduler or pre/post task).

## Content quality ceiling (Plan B/E)
- Off-theme content (grill/Pisa/abstract) persists because candidate pool is
  unchanged and the vision critic is not yet built. Plan B (index/pool) + Plan E
  (VLM critic) are the real fixes. Classic clip dedup (URL/file) works; content
  correctness does not.

## Phase-2 follow-up (logged 2026-09-06, not built)
- Hot-link URL refresh by provider API on stored-URL 404: Pexels/Pixabay masters
  are never stored (license posture) — renders hot-link their stored
  `download_url`. Provider CDN URLs can rot; on a 404 at render time, re-query
  the provider API for a fresh URL for the same clip id and update the index
  row, rather than failing the scene to live fallback. Bound the refresh to one
  retry per clip per render.
