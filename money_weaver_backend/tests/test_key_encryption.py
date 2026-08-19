import os
from src.services.key_encryption import encrypt_key, decrypt_key


def test_roundtrip(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    token = encrypt_key("sk-abc123")
    assert token != "sk-abc123"
    assert decrypt_key(token) == "sk-abc123"


def test_no_secret_key_raises(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    import src.services.key_encryption as ke
    ke._fernet = None
    try:
        encrypt_key("x")
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
