# Plan B Task 0 spike — torch + open-clip ViT-B-32 CPU (2026-09-01)

## Result
- torch==2.2.2 + open-clip-torch==3.3.0 installed in the plan-B venv.
- ViT-B-32 (openai) CPU text embed: **~55-65 ms/text**, 512-dim. Fast enough for ingest.
- Production return path `.tolist()` WORKS.

## Constraint found
- **torch 2.2.2 is incompatible with the venv's numpy==2.2.6**: `tensor.numpy()`
  raises `RuntimeError: Numpy is not available` (the numpy 2.x `_ARRAY_API`
  ABI change). `.tolist()` is unaffected.
- torch 2.4.1 CPU wheel is NOT available for this Python 3.12 / macOS on the
  pytorch CPU index (2.2.2 was the last 3.12 CPU build on that index). So the
  numpy-2 issue cannot be resolved by bumping torch in this env.
- Pinning `numpy<2` (per requirements-ml.txt) would break the rest of the app
  which uses numpy 2.2.6.

## Mitigation baked into the plan
- `TorchEmbedder.embed_text` returns `feat.tolist()` — safe.
- The image-side `.numpy()` path (open-clip preprocess → tensor) is only reached
  by the DEFERRED detectors (scale/move/image embed). Plan B keeps those `None`
  (neutral), so no numpy-on-torch interop is exercised. When detectors ship
  (Phase 2), they must either run torch on a numpy-2-compatible build or convert
  via `.numpy()` only after a torch-numpy-2-compatible upgrade.

## Recommendation
Keep `torch==2.2.2` for Plan B (text embed only). For the Phase-2 detector
upgrade, plan a torch build with numpy-2 support (e.g. torch 2.3+/2.5 via the
default PyPI `torch` with CUDA/CPU, or pin numpy<2 in an isolated ML venv).
