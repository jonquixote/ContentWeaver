import httpx
import pytest
from src.services.providers.base import ProviderError
from src.services.providers.nvidia_nim import NvidiaNimProvider
from src.services.providers.openrouter import OpenRouterProvider


class FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=httpx.Request("GET", "x"), response=httpx.Response(self.status_code, request=httpx.Request("GET", "x")))


def test_openrouter_list_models_normalizes(monkeypatch):
    fake = {
        "data": [
            {"id": "openai/gpt-5.4", "name": "GPT-5.4", "context_length": 400000, "pricing": {"prompt": "0.00001", "completion": "0.00003"}},
            {"id": "nvidia/nemotron-3-nano-30b-a3b:free", "name": "Nemotron Nano", "context_length": 256000, "pricing": {"prompt": "0", "completion": "0"}},
        ]
    }
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(200, fake))
    p = OpenRouterProvider(api_key="k")
    models = p.list_models()
    assert models[0]["id"] == "openai/gpt-5.4"
    assert models[0]["free"] is False
    assert models[1]["free"] is True
    assert models[1]["provider"] == "openrouter"


def test_nvidia_list_models_normalizes(monkeypatch):
    fake = {"data": [{"id": "nvidia/nemotron-3-nano-30b-a3b", "object": "model"}]}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: FakeResponse(200, fake))
    p = NvidiaNimProvider(api_key="k")
    models = p.list_models()
    assert models[0]["provider"] == "nvidia_nim"


def test_chat_returns_content(monkeypatch):
    fake = {"choices": [{"message": {"content": "hello"}}]}
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(200, fake))
    p = OpenRouterProvider(api_key="k")
    assert p.chat("m", [{"role": "user", "content": "hi"}]) == "hello"


def test_chat_raises_provider_error(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResponse(401, {"error": "bad key"}))
    p = NvidiaNimProvider(api_key="bad")
    with pytest.raises(ProviderError):
        p.chat("m", [{"role": "user", "content": "hi"}])
