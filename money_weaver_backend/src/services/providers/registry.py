import threading
import time


class ModelRegistry:
    def __init__(self, providers, ttl=600):
        self.providers = providers
        self.ttl = ttl
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
            self._cache = merged
            self._fetched_at = now
            return list(merged)

    def _models(self):
        return self.list_models()

    def best_free(self, capability="chat"):
        for m in self._models():
            if m["free"] and m["capabilities"].get(capability, False):
                if m["id"] == "openrouter/free":
                    return m["id"]
        for m in self._models():
            if m["free"] and m["capabilities"].get(capability, False):
                return m["id"]
        return None

    def resolve(self, prefs, task, capability="chat"):
        if prefs:
            default = (prefs.get("defaults") or {}).get(task)
            if default:
                return default
            for fb in (prefs.get("fallbacks") or []):
                if fb:
                    return fb
        return self.best_free(capability) or "openrouter/free"

    def provider_for(self, model_id):
        for p in self.providers:
            if model_id.startswith(p.name + "/") or p.name in model_id:
                return p
        return None


registry = ModelRegistry([])
