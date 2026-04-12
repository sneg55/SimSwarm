"""Branch coverage for saas/auth/profile.py.

Covers the "user not found" branch for both change_password and delete_account
and secondary edge cases on delete.
"""
from __future__ import annotations

import jwt
import pytest

from tests.conftest import test_settings

CHANGE_PW_URL = "/api/profile/password"
DELETE_URL = "/api/profile/account"


def _forged_token(user_id: int) -> str:
    """Build a JWT signed with the test SECRET_KEY for an arbitrary user id."""
    return jwt.encode(
        {"sub": str(user_id), "email": "ghost@example.com"},
        test_settings.SECRET_KEY,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_change_password_user_not_found(client):
    """Valid JWT for a non-existent user id returns 404."""
    headers = {"Authorization": f"Bearer {_forged_token(999999)}"}
    resp = await client.put(
        CHANGE_PW_URL,
        json={"current_password": "somepassword", "new_password": "newpassword1"},
        headers=headers,
    )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_account_user_not_found(client):
    """Valid JWT for a non-existent user id returns 404 from the delete path."""
    headers = {"Authorization": f"Bearer {_forged_token(888888)}"}
    resp = await client.delete(DELETE_URL, headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_account_mutates_email_pattern(client, auth_headers, db_session):
    """After soft-delete, the user row's email is rewritten with deleted_<id> pattern."""
    user_id = auth_headers["_user_id"]

    resp = await client.delete(
        DELETE_URL, headers={"Authorization": auth_headers["Authorization"]}
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted"}

    # Fetch user row directly from the DB to confirm the soft-delete pattern.
    from sqlalchemy import select
    from saas.auth.models import User

    result = await db_session.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one()
    assert user.email == f"deleted_{user_id}@deleted"
    assert user.password_hash == ""
