from src.services.footage.sources.registry import (
    SOURCE_REGISTRY, describe_sources, enabled_sources, get_source,
)


def test_registry_has_keyless_and_pond5_not_youtube():
    assert "archive_org" in SOURCE_REGISTRY
    assert "pond5_pd" in SOURCE_REGISTRY
    assert "youtube_cc" not in SOURCE_REGISTRY
    assert "vimeo_cc" not in SOURCE_REGISTRY


def test_get_source_returns_instance():
    src = get_source("archive_org")
    assert src.name == "archive_org"


def test_enabled_sources_honors_env(monkeypatch):
    monkeypatch.setenv("FOOTAGE_SOURCES_ENABLED", "pexels,pixabay")
    names = [s.name for s in enabled_sources()]
    assert set(names) == {"pexels", "pixabay"}


def test_describe_exposes_strengths():
    desc = {d["name"]: d for d in describe_sources()}
    assert "strengths" in desc["archive_org"]
    assert isinstance(desc["archive_org"]["strengths"], list)
    assert "credit_attribution" in desc["archive_org"]
