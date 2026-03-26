import pytest
import jwt

from tests.conftest import test_settings


REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"

VALID_EMAIL = "alice@example.com"
VALID_PASSWORD = "securepass123"


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_success(client):
    """201 response with user object and JWT token."""
    resp = await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    assert resp.status_code == 201
    data = resp.json()
    assert data["user"]["email"] == VALID_EMAIL
    assert isinstance(data["user"]["id"], int)
    assert "token" in data
    assert len(data["token"]) > 20


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    """Second registration with the same email returns 409."""
    payload = {"email": "bob@example.com", "password": "password123"}
    resp1 = await client.post(REGISTER_URL, json=payload)
    assert resp1.status_code == 201
    resp2 = await client.post(REGISTER_URL, json=payload)
    assert resp2.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password(client):
    """Password shorter than 8 characters is rejected."""
    resp = await client.post(REGISTER_URL, json={"email": "carol@example.com", "password": "short"})
    assert resp.status_code in (400, 422)


@pytest.mark.asyncio
async def test_register_invalid_email(client):
    """Non-email string is rejected with 422."""
    resp = await client.post(REGISTER_URL, json={"email": "not-an-email", "password": "validpassword"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success(client):
    """Successful login returns 200 with user + token."""
    await client.post(REGISTER_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    resp = await client.post(LOGIN_URL, json={"email": VALID_EMAIL, "password": VALID_PASSWORD})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == VALID_EMAIL
    assert "token" in data


@pytest.mark.asyncio
async def test_login_wrong_email(client):
    """Login with unknown email returns 401."""
    resp = await client.post(LOGIN_URL, json={"email": "nobody@example.com", "password": "irrelevant"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """Login with correct email but wrong password returns 401."""
    await client.post(REGISTER_URL, json={"email": "dave@example.com", "password": "correctpass"})
    resp = await client.post(LOGIN_URL, json={"email": "dave@example.com", "password": "wrongpass!"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_is_valid_jwt(client):
    """Token returned on registration is a valid HS256 JWT with correct claims."""
    resp = await client.post(REGISTER_URL, json={"email": "eve@example.com", "password": "evepassword"})
    assert resp.status_code == 201
    token = resp.json()["token"]
    user_id = resp.json()["user"]["id"]

    payload = jwt.decode(token, test_settings.SECRET_KEY, algorithms=["HS256"])
    assert payload["sub"] == str(user_id)
    assert payload["email"] == "eve@example.com"
