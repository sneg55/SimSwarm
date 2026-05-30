"""Additional branch coverage for saas/auth/api.py.

Covers short-password reset edge, reset with missing expiry, forgot-password
for unknown email (silent branch), and verify endpoint missing token.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from saas.auth.models import User


REGISTER_URL = "/api/auth/register"
FORGOT_URL = "/api/auth/forgot-password"
RESET_URL = "/api/auth/reset-password"
VERIFY_URL = "/api/auth/verify"


@pytest.mark.asyncio
async def test_reset_password_short_password_returns_422(client):
    """Password shorter than 8 characters is rejected before token lookup."""
    resp = await client.post(RESET_URL, json={"token": "anything", "password": "abc"})
    assert resp.status_code == 422
    assert "8 characters" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reset_password_token_with_null_expiry(client, db_session):
    """Reset token present but reset_token_expires is None — rejected."""
    email = "nullexpiry@example.com"
    await client.post(REGISTER_URL, json={"email": email, "password": "securepass123"})

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.reset_token = "stale-token-xyz"
    user.reset_token_expires = None
    await db_session.commit()

    resp = await client.post(
        RESET_URL, json={"token": "stale-token-xyz", "password": "newsecurepass"}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_with_naive_datetime_expiry(client, db_session):
    """Naive datetime expiry in the future is treated as UTC and accepted."""
    email = "naiveexpiry@example.com"
    await client.post(REGISTER_URL, json={"email": email, "password": "securepass123"})

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.reset_token = "naive-valid-token"
    # naive datetime (no tzinfo) in the future — code must treat as UTC
    user.reset_token_expires = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None)
    await db_session.commit()

    resp = await client.post(
        RESET_URL, json={"token": "naive-valid-token", "password": "newpassword1"}
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_silent(client):
    """Unknown email still returns 200 with the generic message."""
    resp = await client.post(FORGOT_URL, json={"email": "nobody@nowhere.example"})
    assert resp.status_code == 200
    assert "reset link" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_verify_missing_token_422(client):
    """Missing token query param returns 422 from FastAPI validation."""
    resp = await client.get(VERIFY_URL)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_email_format_branch(client):
    """Invalid email format triggers explicit 422 branch (not pydantic)."""
    resp = await client.post(
        REGISTER_URL, json={"email": "no-at-sign-here", "password": "goodpassword"}
    )
    assert resp.status_code == 422
    assert "email" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_short_password_422(client):
    """Password length validated inline, returns 422 with explicit detail."""
    resp = await client.post(
        REGISTER_URL, json={"email": "ok@example.com", "password": "tiny"}
    )
    assert resp.status_code == 422
