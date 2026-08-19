from src.services.providers.base import Provider
from src.services.providers.registry import ModelRegistry


class StubProvider(Provider):
    name = "stub"
    def __init__(self, models, key=None):
        super().__init__(key)
        self._models = models
    def list_models(self):
        return self._models
    def chat(self, model, messages, **kwargs):
        return "ok"


def test_merge_and_free_dedup():
    p1 = StubProvider([
        {"id": "a/free:free", "provider": "stub", "display_name": "A", "capabilities": {"chat": True}, "free": True, "context_window": 100},
        {"id": "a/paid", "provider": "stub", "display_name": "B", "capabilities": {"chat": True}, "free": False, "context_window": 100},
    ])
    p2 = StubProvider([
        {"id": "b/free:free", "provider": "stub", "display_name": "C", "capabilities": {"chat": True}, "free": True, "context_window": 100},
    ])
    reg = ModelRegistry([p1, p2])
    models = reg.list_models()
    assert len(models) == 3


def test_best_free_returns_free_chat_model():
    p = StubProvider([
        {"id": "a/paid", "provider": "stub", "display_name": "B", "capabilities": {"chat": True}, "free": False, "context_window": 100},
        {"id": "b/cheap:free", "provider": "stub", "display_name": "C", "capabilities": {"chat": True}, "free": True, "context_window": 100},
    ])
    reg = ModelRegistry([p])
    assert reg.best_free() == "b/cheap:free"


def test_resolve_prefers_user_default_then_fallback_then_free():
    p = StubProvider([
        {"id": "a/default", "provider": "stub", "display_name": "D", "capabilities": {"chat": True}, "free": False, "context_window": 100},
        {"id": "a/fallback", "provider": "stub", "display_name": "F", "capabilities": {"chat": True}, "free": False, "context_window": 100},
        {"id": "a/free:free", "provider": "stub", "display_name": "G", "capabilities": {"chat": True}, "free": True, "context_window": 100},
    ])
    reg = ModelRegistry([p])
    prefs = {"defaults": {"script": "a/default"}, "fallbacks": ["a/fallback"]}
    assert reg.resolve(prefs, "script") == "a/default"
    assert reg.resolve({"defaults": {}, "fallbacks": ["a/fallback"]}, "script") == "a/fallback"
    assert reg.resolve(None, "script") == "a/free:free"
