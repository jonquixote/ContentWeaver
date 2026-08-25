import os

import httpx

from .base import Provider, ProviderError

OR_BASE = "https://openrouter.ai/api/v1"


def _free(pricing):
    return (pricing or {}).get("prompt") in ("0", 0, "0.0")


class OpenRouterProvider(Provider):
    name = "openrouter"
    base_url = OR_BASE

    def _env_key(self):
        return os.getenv("OPENROUTER_API_KEY")

    def list_models(self):
        r = httpx.get(f"{self.base_url}/models", timeout=30)
        r.raise_for_status()
        out = []
        for m in r.json().get("data", []):
            out.append(
                {
                    "id": m["id"],
                    "provider": self.name,
                    "kind": "text",
                    "display_name": m.get("name", m["id"]),
                    "capabilities": {"chat": True, "image": False, "audio": False},
                    "free": _free(m.get("pricing")),
                    "context_window": m.get("context_length", 0),
                }
            )
        return out

    def chat(self, model, messages, **kwargs):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        payload = {"model": model, "messages": messages, **kwargs}
        r = httpx.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=120)
        if r.status_code >= 400:
            text = getattr(r, "text", None)
            if text is None:
                try:
                    text = str(r.json())
                except Exception:
                    text = ""
            raise ProviderError(f"openrouter {r.status_code}: {text[:200]}")
        return r.json()["choices"][0]["message"]["content"]
