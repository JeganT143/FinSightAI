"""Authentication (SAAS §3): verify Clerk-issued JWTs, provision users on
first sight.

Clerk owns passwords/MFA/OAuth; this module only ever sees a signed token.
Verification is local (RS256 against the issuer's JWKS, cached) — no network
call to Clerk on the request path except the rare JWKS refresh.

`auth_mode="disabled"` preserves Phase-1 single-operator behavior for local
dev: every request acts as one stable dev user. main.py refuses to stay
quiet about this outside debug.
"""

import logging
import time

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.db.models import User
from backend.db.session import get_db

logger = logging.getLogger(__name__)

_JWKS_TTL_SECONDS = 3600
_DEV_USER_EMAIL = "dev@localhost"


class _JwksCache:
    """kid -> public key, refreshed from the issuer at most once per TTL."""

    def __init__(self) -> None:
        self._keys: dict[str, object] = {}
        self._fetched_at = 0.0

    async def get_key(self, kid: str) -> object:
        if kid not in self._keys or time.monotonic() - self._fetched_at > _JWKS_TTL_SECONDS:
            await self._refresh()
        key = self._keys.get(kid)
        if key is None:
            raise HTTPException(status_code=401, detail="Unknown signing key")
        return key

    async def _refresh(self) -> None:
        url = f"{settings.clerk_issuer.rstrip('/')}/.well-known/jwks.json"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        self._keys = {k["kid"]: jwt.PyJWK(k).key for k in resp.json().get("keys", []) if "kid" in k}
        self._fetched_at = time.monotonic()


_jwks = _JwksCache()


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


async def _verify_clerk_token(token: str) -> dict:
    """Signature + expiry + issuer (+ optional azp allowlist) -> claims."""
    try:
        kid = jwt.get_unverified_header(token).get("kid", "")
        key = await _jwks.get_key(kid)
        claims: dict = jwt.decode(
            token,
            key=key,  # type: ignore[arg-type]  # PyJWK.key is the loaded public key
            algorithms=["RS256"],
            issuer=settings.clerk_issuer.rstrip("/"),
            options={"verify_aud": False},  # Clerk session tokens carry azp, not aud
        )
    except HTTPException:
        raise
    except jwt.PyJWTError as e:
        # Class name only — token contents/why are for the log, not the client.
        logger.info("JWT rejected: %s", type(e).__name__)
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    if settings.clerk_authorized_parties:
        if claims.get("azp") not in settings.clerk_authorized_parties:
            raise HTTPException(status_code=401, detail="Token not issued for this application")
    return claims


async def _get_or_create_user(db: AsyncSession, external_auth_id: str, email: str) -> User:
    """Just-in-time provisioning (SAAS §3.4): first verified token creates the row.

    Committed immediately: tools and the SSE stream read through their own
    sessions, which can't see this session's uncommitted insert.
    """
    result = await db.execute(select(User).where(User.external_auth_id == external_auth_id))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(external_auth_id=external_auth_id, email=email, plan="free")
    db.add(user)
    await db.commit()
    logger.info("provisioned user %s (plan=free)", user.id)
    return user


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    """FastAPI dependency: the verified caller, provisioned on first sight."""
    if settings.auth_mode == "disabled":
        result = await db.execute(select(User).where(User.email == _DEV_USER_EMAIL))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(email=_DEV_USER_EMAIL, plan="pro")  # dev user gets full routing
            db.add(user)
            await db.commit()
        return user

    token = _bearer_token(request)
    claims = await _verify_clerk_token(token)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Token missing subject")
    email = claims.get("email") or f"{sub}@users.clerk"
    return await _get_or_create_user(db, external_auth_id=sub, email=email)
