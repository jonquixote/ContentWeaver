import os

from src.services.cinema.cache import cache_dir


def test_cache_dir_uses_env(monkeypatch):
    monkeypatch.setenv("CINEMA_CACHE_DIR", "/tmp/cw-cinema-test")
    assert str(cache_dir()) == "/tmp/cw-cinema-test"


def test_cache_dir_defaults_under_tmp(monkeypatch):
    monkeypatch.delenv("CINEMA_CACHE_DIR", raising=False)
    assert "cinema" in str(cache_dir())
