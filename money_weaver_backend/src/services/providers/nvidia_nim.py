import os

import httpx

from .base import Provider, ProviderError

NV_BASE = "https://integrate.api.nvidia.com/v1"


class NvidiaNimProvider(Provider):
    name = "nvidia_nim"
    base_url = NV_BASE

    def _env_key(self):
        return os.getenv("NVIDIA_API_KEY")

    def list_models(self):
        headers = {"Authorization": f"Bearer {self.api_key}"}
        r = httpx.get(f"{self.base_url}/models", headers=headers, timeout=30)
        r.raise_for_status()
        out = []
        for m in r.json().get("data", []):
            mid = m["id"]
            out.append(
                {
                    "id": mid,
                    "provider": self.name,
                    "display_name": m.get("id", mid),
                    "capabilities": {"chat": True, "image": False, "audio": False},
                    "free": ":free" in mid or ":test" in mid,
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
            raise ProviderError(f"nvidia {r.status_code}: {text[:200]}")
        return r.json()["choices"][0]["message"]["content"]
