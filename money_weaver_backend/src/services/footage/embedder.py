from __future__ import annotations

import os

from abc import ABC, abstractmethod


class Embedder(ABC):
    """Text embedding provider. Backends: none | torch | onnx | hosted_gemini."""

    @abstractmethod
    def embed_text(self, s: str) -> list[float]:
        ...


class NoneEmbedder(Embedder):
    """Disabled: returns empty vector. Tests pass with this default."""

    def embed_text(self, s: str) -> list[float]:
        return []


class _RemoteEmbedder(Embedder):
    """Proxy to a hosted API (Gemini by default) for text embedding."""

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("EMBED_MODEL", "ViT-B-32")
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("OPENROUTER_API_KEY")

    def embed_text(self, s: str) -> list[float]:
        raise NotImplementedError("hosted embedding wired via the LLM path in a later phase")


class TorchEmbedder(Embedder):
    """CPU open-clip ViT-B-32. Only imported when EMBED_BACKEND=torch.

    Returns feat.tolist() — NOT feat.numpy() — because torch 2.2.2 is
    incompatible with numpy 2.x in this env (numpy() raises). Text embedding
    via .tolist() is verified working (~55-65 ms/text on CPU).
    """

    def __init__(self, model: str, pretrained: str = "openai"):
        import open_clip  # heavy, flagged (EMBED_BACKEND=torch)
        self.model = model
        self.pretrained = pretrained
        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            model, pretrained=pretrained
        )
        self._tokenizer = open_clip.get_tokenizer(model)

    def embed_text(self, s: str) -> list[float]:
        import torch  # noqa: F401
        tokens = self._tokenizer([s])
        with torch.no_grad():
            feat = self._model.encode_text(tokens)
        return feat[0].tolist()


class OnnxEmbedder(Embedder):
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("EMBED_MODEL", "ViT-B-32")

    def embed_text(self, s: str) -> list[float]:
        raise NotImplementedError("onnxruntime backend: load .onnx CLIP text encoder")


class HostedGeminiEmbedder(_RemoteEmbedder):
    pass


def make_embedder() -> Embedder:
    backend = os.getenv("EMBED_BACKEND", "none").lower()
    model = os.getenv("EMBED_MODEL", "ViT-B-32")
    if backend == "torch":
        return TorchEmbedder(model)
    if backend == "onnx":
        return OnnxEmbedder(model)
    if backend == "hosted_gemini":
        return HostedGeminiEmbedder(model)
    return NoneEmbedder()
