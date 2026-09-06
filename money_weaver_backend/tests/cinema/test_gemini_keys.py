import time

from src.services.cinema import gemini_keys as gk


def _env(monkeypatch, primary="K1", fallbacks="K2,K3"):
    monkeypatch.setenv("GEMINI_API_KEY", primary)
    monkeypatch.setenv("GEMINI_API_KEY_FALLBACKS", fallbacks)
    gk.reset_cooldowns()


def test_get_keys_order_and_dedup(monkeypatch):
    _env(monkeypatch, primary="K1", fallbacks="K2,K1,K3")
    assert gk.get_keys() == ["K1", "K2", "K3"]


def test_get_keys_empty_without_env(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY_FALLBACKS", raising=False)
    gk.reset_cooldowns()
    assert gk.get_keys() == []


def test_exhausted_key_skipped_then_recovers(monkeypatch):
    _env(monkeypatch)
    gk.mark_exhausted("K1", cooldown_s=1000)
    assert gk.live_keys() == ["K2", "K3"]
    gk.mark_ok("K1")
    assert gk.live_keys() == ["K1", "K2", "K3"]


def test_cooldown_expires(monkeypatch):
    _env(monkeypatch)
    gk.mark_exhausted("K1", cooldown_s=0)
    time.sleep(0.01)
    assert "K1" in gk.live_keys()


def test_all_exhausted_yields_empty(monkeypatch):
    _env(monkeypatch, primary="K1", fallbacks="K2")
    gk.mark_exhausted("K1", cooldown_s=1000)
    gk.mark_exhausted("K2", cooldown_s=1000)
    assert gk.live_keys() == []
