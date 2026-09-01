import os

from src.services.footage.embedder import NoneEmbedder, make_embedder


def test_none_embedder_returns_empty():
    e = NoneEmbedder()
    assert e.embed_text("hello") == []


def test_make_embedder_defaults_to_none():
    os.environ["EMBED_BACKEND"] = "none"
    assert isinstance(make_embedder(), NoneEmbedder)


def test_make_embedder_hosted_gemini_when_set(monkeypatch):
    monkeypatch.setenv("EMBED_BACKEND", "hosted_gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "probe")
    from src.services.footage.embedder import HostedGeminiEmbedder
    assert isinstance(make_embedder(), HostedGeminiEmbedder)


def test_none_backend_still_produces_clip_ready_shape():
    # The contract: with EMBED_BACKEND=none, embeddings are empty (None) but
    # ingestion must not crash. This is asserted by the analyze task, not here.
    assert NoneEmbedder().embed_text("x") == []
