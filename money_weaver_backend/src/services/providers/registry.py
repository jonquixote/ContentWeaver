import threading
import time

# Known-good free models, tried in order before falling back to any catalog
# :free entry. Non-reasoning models preferred (reasoning models put CoT in
# content or empty it entirely). Verified against live OpenRouter 2026-08.
PREFERRED_FREE_MODELS = [
    "poolside/laguna-s-2.1:free",
    "dots-studio/dots-3-note-preview:free",
    "nvidia/nemotron-3.5-lightning:free",
]

# Pseudo-ids that appear in catalogs but 404 on completions.
UNUSABLE_MODEL_IDS = {"openrouter/free"}

# Optional catalog sources appended by provider adapters (e.g. fal_adapter).
# Each source is a zero-arg callable returning a list of model dicts; failures
# are skipped so one broken provider never blocks the merged catalog.
EXTRA_CATALOG_SOURCES = []


class ModelRegistry:
    def __init__(self, providers, ttl=600, include_extra_catalogs=False):
        """include_extra_catalogs: merge adapter-registered catalogs
        (EXTRA_CATALOG_SOURCES). Off by default so standalone/instance-scoped
        registries stay deterministic; the shared hub registry opts in."""
        self.providers = providers
        self.ttl = ttl
        self.include_extra_catalogs = include_extra_catalogs
        self._cache = None
        self._fetched_at = 0.0
        self._lock = threading.Lock()

    def list_models(self, force=False):
        with self._lock:
            now = time.time()
            if self._cache is not None and not force and (now - self._fetched_at) < self.ttl:
                return list(self._cache)
            merged = []
            seen = set()
            for p in self.providers:
                try:
                    for m in p.list_models():
                        if m["id"] not in seen:
                            seen.add(m["id"])
                            merged.append(m)
                except Exception:
                    continue
            if self.include_extra_catalogs:
                for source in EXTRA_CATALOG_SOURCES:
                    try:
                        for m in source():
                            if m["id"] not in seen:
                                seen.add(m["id"])
                                merged.append(m)
                    except Exception:
                        continue
            self._cache = merged
            self._fetched_at = now
            return list(merged)

    def _models(self):
        return self.list_models()

    def best_free(self, capability="chat"):
        catalog_ids = {
            m["id"] for m in self._models()
            if m["free"] and (m.get("capabilities") or {}).get(capability, False)
        }
        # 1. known-good candidates that are actually in the catalog
        for candidate in PREFERRED_FREE_MODELS:
            if candidate in catalog_ids:
                return candidate
        # 2. any real free model, excluding pseudo-ids
        usable = sorted(catalog_ids - UNUSABLE_MODEL_IDS)
        if usable:
            return usable[0]
        return None

    def resolve(self, prefs, task, capability="chat"):
        if prefs:
            default = (prefs.get("defaults") or {}).get(task)
            if default:
                return default
            for fb in (prefs.get("fallbacks") or []):
                if fb:
                    return fb
        return self.best_free(capability) or PREFERRED_FREE_MODELS[0]

    def provider_for(self, model_id):
        for p in self.providers:
            if model_id.startswith(p.name + "/") or p.name in model_id:
                return p
        return None


registry = ModelRegistry([], include_extra_catalogs=True)
