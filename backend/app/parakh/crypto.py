"""Encrypt broker access tokens at rest (Fernet / AES-128-CBC + HMAC)."""
from __future__ import annotations

import base64
import hashlib

from app.config import get_settings

_DEV_KEY_SEED = b"parakh-local-dev-only-not-secret"


def _fernet():
    from cryptography.fernet import Fernet
    s = get_settings()
    key = s.TOKEN_ENCRYPTION_KEY
    if not key:
        if s.is_production:
            raise RuntimeError("TOKEN_ENCRYPTION_KEY must be set in production")
        key = base64.urlsafe_b64encode(hashlib.sha256(_DEV_KEY_SEED).digest()).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
