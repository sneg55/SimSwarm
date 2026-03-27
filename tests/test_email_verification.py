"""Tests for email verification and password reset endpoints."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from saas.models.user import User


REGISTER_URL = "/api/auth/register"
VERIFY_URL = "/api/auth/verify"
FORGOT_URL = "/api/auth/forgot-password"
RESET_URL = "/api/auth/reset-password"

VALID_EMAIL = "verifytest@example.com"
VALID_PASSWORD = "securepass123"


# ---------------------------------------------------------------------------
# Email Verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_returns_unverified_user(client):
    """Newly registered user should have email_verified=False."""
    resp = await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email_verified"] is False


@pytest.mark.asyncio
async def test_verify_email_with_valid_token(client, db_session):
    """Valid token sets email_verified=True and clears the token."""
    resp = await client.post(REGISTER_URL, json={"email": "verify1@example.com", "password": VALID_PASSWORD})
    assert resp.status_code == 201

    # Fetch the token directly from the DB
    result = await db_session.execute(select(User).where(User.email == "verify1@example.com"))
    user = result.scalar_one()
    token = user.verification_token
    assert token is not None

    resp = await client.get(f"{VERIFY_URL}?token={token}")
    assert resp.status_code == 200
    assert resp.json()["message"] == "Email verified successfully"

    # Confirm DB state
    await db_session.refresh(user)
    assert user.email_verified is True
    assert user.verification_token is None


@pytest.mark.asyncio
async def test_verify_email_with_invalid_token(client):
    """Invalid token returns 400."""
    resp = await client.get(f"{VERIFY_URL}?token=totally-wrong-token")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Forgot Password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forgot_password_returns_200(client):
    """forgot-password always returns 200 regardless of whether email exists."""
    # Known email
    await client.post(REGISTER_URL, json={"email": "forgot1@example.com", "password": VALID_PASSWORD})
    resp = await client.post(FORGOT_URL, json={"email": "forgot1@example.com"})
    assert resp.status_code == 200

    # Unknown email — still 200 (don't leak info)
    resp2 = await client.post(FORGOT_URL, json={"email": "ghost@example.com"})
    assert resp2.status_code == 200


# ---------------------------------------------------------------------------
# Reset Password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reset_password_with_valid_token(client, db_session):
    """Valid reset token allows changing the password."""
    email = "resetvalid@example.com"
    await client.post(REGISTER_URL, json={"email": email, "password": VALID_PASSWORD})
    await client.post(FORGOT_URL, json={"email": email})

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    token = user.reset_token
    assert token is not None

    new_password = "newpassword999"
    resp = await client.post(RESET_URL, json={"token": token, "password": new_password})
    assert resp.status_code == 200
    assert resp.json()["message"] == "Password reset successfully"

    # Confirm old password no longer works, new one does
    login_old = await client.post("/api/auth/login", json={"email": email, "password": VALID_PASSWORD})
    assert login_old.status_code == 401

    login_new = await client.post("/api/auth/login", json={"email": email, "password": new_password})
    assert login_new.status_code == 200

    # Token should be cleared
    await db_session.refresh(user)
    assert user.reset_token is None
    assert user.reset_token_expires is None


@pytest.mark.asyncio
async def test_reset_password_with_expired_token(client, db_session):
    """Expired reset token is rejected with 400."""
    email = "resetexpired@example.com"
    await client.post(REGISTER_URL, json={"email": email, "password": VALID_PASSWORD})
    await client.post(FORGOT_URL, json={"email": email})

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    token = user.reset_token

    # Manually expire the token
    user.reset_token_expires = datetime.now(timezone.utc) - timedelta(hours=2)
    await db_session.commit()

    resp = await client.post(RESET_URL, json={"token": token, "password": "brandnewpass"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_reset_password_with_invalid_token(client):
    """Invalid reset token returns 400."""
    resp = await client.post(RESET_URL, json={"token": "bogus-token", "password": "somepassword"})
    assert resp.status_code == 400
