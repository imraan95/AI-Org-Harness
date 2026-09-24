"""T051: verify a logged-in web user's Supabase Auth session token.

Confirmed against this project's real local Supabase instance (not
assumed): `GET {SUPABASE_URL}/auth/v1/.well-known/jwks.json` returns a
single ES256 (asymmetric) key. This project is on Supabase's newer JWT
Signing Keys system, not the legacy shared HS256 secret that
docs/architecture.md's "JWT secret/JWKS" wording anticipated as one of two
possibilities - so this verifies via JWKS, not a static secret.
"""

from __future__ import annotations

import os

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient

DEFAULT_SUPABASE_URL = "http://127.0.0.1:54321"

_SUPABASE_URL = os.environ.get("SUPABASE_URL", DEFAULT_SUPABASE_URL)
# PyJWKClient caches the fetched JWKS in memory and re-fetches on a
# key-id it doesn't recognise (e.g. after rotation) - one client is fine
# to share across requests, unlike the per-request OpenViking/DB clients
# elsewhere in this codebase, since this doesn't hold an event-loop-bound
# connection.
_jwks_client = PyJWKClient(f"{_SUPABASE_URL}/auth/v1/.well-known/jwks.json")


async def get_current_user(request: Request) -> dict:
    """FastAPI dependency: 401s on a missing/invalid/expired token,
    otherwise returns the token's decoded claims (includes `sub` = the
    Supabase user id, `email`, etc.).
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = auth_header.removeprefix("Bearer ").strip()

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token, signing_key.key, algorithms=["ES256"], audience="authenticated"
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
