"""Tests for saas.auth.dependencies.get_current_user."""
import pytest
from fastapi import HTTPException
from unittest.mock import MagicMock

from saas.auth.dependencies import get_current_user


class _Settings:
    SECRET_KEY = "test-secret"


def _make_request():
    req = MagicMock()
    req.app.state.settings = _Settings()
    return req


async def test_get_current_user_no_credentials_raises_401():
    req = _make_request()
    with pytest.raises(HTTPException) as ei:
        await get_current_user(req, credentials=None)
    assert ei.value.status_code == 401
    assert "Not authenticated" in ei.value.detail


async def test_get_current_user_invalid_token_raises_401():
    from fastapi.security import HTTPAuthorizationCredentials

    req = _make_request()
    bad_creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")
    with pytest.raises(HTTPException) as ei:
        await get_current_user(req, credentials=bad_creds)
    assert ei.value.status_code == 401


async def test_get_current_user_valid_token_returns_payload():
    from fastapi.security import HTTPAuthorizationCredentials
    from saas.auth.service import create_token

    req = _make_request()
    token = create_token(user_id=42, email="a@b.com", secret_key="test-secret")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    out = await get_current_user(req, credentials=creds)
    assert out["user_id"] == "42"
    assert out["email"] == "a@b.com"
