"""Clerk JWT verification tests (SAAS §3) — a locally generated RSA keypair
stands in for Clerk's JWKS; no network, no Clerk account needed."""

import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import select

from backend.core import auth as auth_module
from backend.core.config import settings
from backend.db.models import User

ISSUER = "https://test-app.clerk.accounts.dev"
KID = "test-key"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def mint_token(
    sub: str = "user_clerk_abc",
    email: str | None = "person@example.com",
    issuer: str = ISSUER,
    expires_in: int = 600,
    kid: str = KID,
    azp: str | None = None,
) -> str:
    now = datetime.now(UTC)
    claims: dict = {
        "sub": sub,
        "iss": issuer,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    if email:
        claims["email"] = email
    if azp:
        claims["azp"] = azp
    return jwt.encode(claims, _private_key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def clerk_mode(monkeypatch):
    """Switch auth on and point verification at the test keypair."""
    monkeypatch.setattr(settings, "auth_mode", "clerk")
    monkeypatch.setattr(settings, "clerk_issuer", ISSUER)
    monkeypatch.setattr(settings, "clerk_authorized_parties", [])
    monkeypatch.setattr(auth_module._jwks, "_keys", {KID: _private_key.public_key()})
    monkeypatch.setattr(auth_module._jwks, "_fetched_at", time.monotonic())

    async def no_network_refresh():
        raise AssertionError("JWKS refresh must not hit the network in tests")

    monkeypatch.setattr(auth_module._jwks, "_refresh", no_network_refresh)


async def test_no_token_is_401(client, clerk_mode):
    resp = await client.get("/api/reports")
    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


async def test_valid_token_provisions_user_just_in_time(client, clerk_mode, db_session):
    token = mint_token(sub="user_new_123", email="new@example.com")
    resp = await client.get("/api/reports", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200

    user = (
        await db_session.execute(select(User).where(User.external_auth_id == "user_new_123"))
    ).scalar_one()
    assert user.email == "new@example.com"
    assert user.plan == "free"  # new accounts start free, always

    # Second request with the same subject reuses the row, not a duplicate.
    resp = await client.get("/api/reports", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    count = len(
        (await db_session.execute(select(User).where(User.external_auth_id == "user_new_123")))
        .scalars()
        .all()
    )
    assert count == 1


async def test_expired_token_is_401(client, clerk_mode):
    token = mint_token(expires_in=-60)
    resp = await client.get("/api/reports", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid or expired token"


async def test_wrong_issuer_is_401(client, clerk_mode):
    token = mint_token(issuer="https://evil.example.com")
    resp = await client.get("/api/reports", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_garbage_token_is_401(client, clerk_mode):
    resp = await client.get("/api/reports", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401


async def test_azp_allowlist_enforced_when_configured(client, clerk_mode, monkeypatch):
    monkeypatch.setattr(settings, "clerk_authorized_parties", ["https://finsightai.jegant.dev"])

    wrong = mint_token(azp="https://attacker.example.com")
    resp = await client.get("/api/reports", headers={"Authorization": f"Bearer {wrong}"})
    assert resp.status_code == 401

    right = mint_token(azp="https://finsightai.jegant.dev")
    resp = await client.get("/api/reports", headers={"Authorization": f"Bearer {right}"})
    assert resp.status_code == 200


async def test_disabled_mode_resolves_stable_dev_user(client, db_session):
    # Default test settings: auth_mode="disabled". Two requests, one user row.
    assert (await client.get("/api/reports")).status_code == 200
    assert (await client.get("/api/reports")).status_code == 200
    users = (
        (await db_session.execute(select(User).where(User.email == "dev@localhost")))
        .scalars()
        .all()
    )
    assert len(users) == 1


async def test_report_detail_404_for_other_tenants_via_api(client, clerk_mode, db_session):
    """End-to-end §5 check through the HTTP surface, not just crud."""
    from tests.test_api import seed_report

    owner = User(email="owner@example.com", external_auth_id="user_owner", plan="pro")
    db_session.add(owner)
    await db_session.commit()
    report = await seed_report(db_session, owner.id)

    intruder_token = mint_token(sub="user_intruder", email="intruder@example.com")
    resp = await client.get(
        f"/api/reports/{report.id}", headers={"Authorization": f"Bearer {intruder_token}"}
    )
    assert resp.status_code == 404  # not 403 — existence itself must not leak

    owner_token = mint_token(sub="user_owner", email="owner@example.com")
    resp = await client.get(
        f"/api/reports/{report.id}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert resp.status_code == 200
