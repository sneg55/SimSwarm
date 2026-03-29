import pytest

CHANGE_PW_URL = "/api/profile/password"
DELETE_URL = "/api/profile/account"


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_change_password_success(client, auth_headers):
    """Successfully changing password returns 200 with status ok."""
    resp = await client.put(
        CHANGE_PW_URL,
        json={"current_password": "testpass123", "new_password": "newpassword1"},
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_change_password_wrong_current(client, auth_headers):
    """Wrong current password returns 400."""
    resp = await client.put(
        CHANGE_PW_URL,
        json={"current_password": "wrongpassword", "new_password": "newpassword1"},
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_change_password_too_short(client, auth_headers):
    """New password shorter than 8 characters returns 422."""
    resp = await client.put(
        CHANGE_PW_URL,
        json={"current_password": "testpass123", "new_password": "short"},
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_change_password_unauthenticated(client):
    """No auth token returns 401 or 403."""
    resp = await client.put(
        CHANGE_PW_URL,
        json={"current_password": "testpass123", "new_password": "newpassword1"},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_change_password_new_password_works(client, auth_headers):
    """After changing password the new password can log in."""
    # Change password
    resp = await client.put(
        CHANGE_PW_URL,
        json={"current_password": "testpass123", "new_password": "brandnewpass"},
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert resp.status_code == 200

    # Login with new password
    resp = await client.post(
        "/api/auth/login",
        json={"email": "testuser@example.com", "password": "brandnewpass"},
    )
    assert resp.status_code == 200
    assert "token" in resp.json()


# ---------------------------------------------------------------------------
# Delete account
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_account_success(client, auth_headers):
    """Deleting account returns 200 with status deleted."""
    resp = await client.delete(
        DELETE_URL,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "deleted"}


@pytest.mark.asyncio
async def test_delete_account_unauthenticated(client):
    """No auth token returns 401 or 403."""
    resp = await client.delete(DELETE_URL)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_delete_account_cannot_login_after(client, auth_headers):
    """After soft-delete, old email cannot log in."""
    # Delete account
    resp = await client.delete(
        DELETE_URL,
        headers={"Authorization": auth_headers["Authorization"]},
    )
    assert resp.status_code == 200

    # Attempt login with original email should fail
    resp = await client.post(
        "/api/auth/login",
        json={"email": "testuser@example.com", "password": "testpass123"},
    )
    assert resp.status_code == 401
