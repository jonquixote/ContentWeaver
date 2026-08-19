import os
from cryptography.fernet import Fernet
import base64
import hashlib

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY is not set")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    _fernet = Fernet(key)
    return _fernet


def encrypt_key(plain):
    return _get_fernet().encrypt(plain.encode()).decode()


def decrypt_key(token):
    return _get_fernet().decrypt(token.encode()).decode()
