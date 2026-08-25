from src.services import llm_service
from src.services.llm_service import llm_service as svc


def test_build_registry_wires_providers(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or")
    monkeypatch.setenv("NVIDIA_API_KEY", "nv")
    svc.build_registry()
    from src.services.providers.registry import registry
    assert len(registry.providers) >= 1


def test_generate_idea_shape(monkeypatch):
    class FakeProvider:
        name = "openrouter"
        def chat(self, model, messages, **kw):
            return '{"title":"X","topic":"Y","script":"**Scene 1**\\nAction line\\nNARRATOR\\nHello"}'  # noqa: E501
        def list_models(self):
            return [{"id": "openrouter/free", "provider": "openrouter", "display_name": "r",
                     "capabilities": {"chat": True}, "free": True, "context_window": 1000}]

    svc.build_registry(providers=[FakeProvider()])
    idea = svc.generate_idea(seed="space")
    assert idea["title"] == "X"
    assert "script" in idea


def test_generate_script_returns_string_on_provider_error(monkeypatch):
    class BadProvider:
        name = "openrouter"
        def chat(self, *a, **kw):
            raise Exception("boom")
        def list_models(self):
            return []
    svc.build_registry(providers=[BadProvider()])
    out = svc.generate_script("topic", user_id=1)
    assert isinstance(out, str) and len(out) > 0


def test_chat_free_resilient_exhaustion_raises_runtime_error():
    """All free candidates 429 -> RuntimeError with last error message
    (regression: except-as-e previously raised UnboundLocalError)."""
    from src.services.providers.base import ProviderError

    class RateLimitedProvider:
        name = "openrouter"
        def chat(self, *a, **kw):
            raise ProviderError("429 rate limited")

    svc.build_registry(providers=[RateLimitedProvider()])
    import pytest
    with pytest.raises(RuntimeError) as exc_info:
        svc._chat_free_resilient(1, "some-model:free", [{"role": "user",
                                                         "content": "hi"}])
    msg = str(exc_info.value)
    assert "all free models exhausted" in msg
    assert "429" in msg
