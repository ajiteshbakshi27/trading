"""
Parakh — authentication.

Production: verifies Supabase Auth access tokens (JWT).
  * New Supabase projects sign with asymmetric keys -> verified against the
    project's JWKS endpoint ({SUPABASE_URL}/auth/v1/.well-known/jwks.json).
  * Projects still on the legacy shared secret -> HS256 with
    SUPABASE_JWT_SECRET.

Development (no Supabase configured AND ENVIRONMENT != production): requests
are attributed to a local dev user so the app works with zero setup. The
user id can be overridden with the X-Parakh-Dev-User header to test
multi-user isolation. Dev mode is refused in production.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from fastapi import HTTPException, Request

from app.config import get_settings

DEV_USER_ID = "dev-user"
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.@-]{1,64}$")


@dataclass(frozen=True)
class User:
    id: str
    email: str = ""
    name: str = ""
    mode: str = "supabase"  # "supabase" | "dev"


@lru_cache(maxsize=4)
def _jwks_client(url: str):
    import jwt  # PyJWT
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def _decode(token: str) -> dict:
    import jwt
    s = get_settings()
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "")
    if alg == "HS256":
        if not s.SUPABASE_JWT_SECRET:
            raise jwt.InvalidTokenError("HS256 token but no SUPABASE_JWT_SECRET")
        return jwt.decode(token, s.SUPABASE_JWT_SECRET, algorithms=["HS256"],
                          audience="authenticated")
    if not s.SUPABASE_URL:
        raise jwt.InvalidTokenError("asymmetric token but no SUPABASE_URL")
    jwks = _jwks_client(s.SUPABASE_URL.rstrip("/") + "/auth/v1/.well-known/jwks.json")
    key = jwks.get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["ES256", "RS256", "EdDSA"],
                      audience="authenticated")


def _bearer(request: Request) -> str:
    h = request.headers.get("authorization", "")
    return h[7:].strip() if h.lower().startswith("bearer ") else ""


def resolve_user(request: Request) -> Optional[User]:
    """Return the caller, or None when unauthenticated. Never raises 5xx."""
    s = get_settings()
    token = _bearer(request)
    if s.auth_configured:
        if not token:
            return None
        try:
            claims = _decode(token)
        except Exception:
            return None
        meta = claims.get("user_metadata") or {}
        return User(id=str(claims.get("sub", "")), email=str(claims.get("email", "")),
                    name=str(meta.get("name") or meta.get("full_name") or ""),
                    mode="supabase")
    if s.is_production:
        return None
    dev = request.headers.get("x-parakh-dev-user", "").strip() or DEV_USER_ID
    if not _SAFE_ID.match(dev):
        dev = DEV_USER_ID
    return User(id=dev, email=f"{dev}@local", name="Local dev", mode="dev")


def require_user(request: Request) -> User:
    """FastAPI dependency: 401 unless the caller is authenticated."""
    user = resolve_user(request)
    if user is None or not user.id:
        s = get_settings()
        if s.is_production and not s.auth_configured:
            raise HTTPException(status_code=503,
                                detail="Sign-in is not configured on this server.")
        raise HTTPException(status_code=401, detail="Please sign in.")
    return user


def optional_user(request: Request) -> Optional[User]:
    return resolve_user(request)


def require_admin(request: Request) -> User:
    """Operator-only endpoints (live broker orders, kill switch).
    Production: the user's email must be in ADMIN_EMAILS. Dev: any user."""
    user = require_user(request)
    s = get_settings()
    if s.is_production and user.email.lower() not in s.ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Operator access only.")
    return user
