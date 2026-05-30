"""Tests for rate limiting on auth endpoints."""
import pytest


REGISTER_URL = "/api/auth/register"
LOGIN_URL = "/api/auth/login"


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset the shared in-memory rate-limiter before each test."""
    from saas.limiter import limiter
    limiter.reset()
    yield
    limiter.reset()


async def test_register_rate_limited_after_5_requests(client):
    """6th register attempt from the same IP within a minute should return 429."""
    # Make 5 allowed requests (some may succeed, some may fail with 409/422)
    for i in range(5):
        await client.post(
            REGISTER_URL,
            json={"email": f"ratelimit_reg{i}@example.com", "password": "password123"},
        )

    # The 6th request should be rate limited
    resp = await client.post(
        REGISTER_URL,
        json={"email": "ratelimit_reg_over@example.com", "password": "password123"},
    )
    assert resp.status_code == 429


async def test_login_rate_limited_after_10_requests(client):
    """11th login attempt from the same IP within a minute should return 429."""
    # Register one user first (does not count against login limit)
    from saas.limiter import limiter
    limiter.reset()

    await client.post(
        REGISTER_URL,
        json={"email": "ratelimit_login@example.com", "password": "password123"},
    )

    # Reset again so register call doesn't affect login limit
    limiter.reset()

    # Make 10 login attempts
    for i in range(10):
        await client.post(
            LOGIN_URL,
            json={"email": "ratelimit_login@example.com", "password": "wrongpass"},
        )

    # The 11th request should be rate limited
    resp = await client.post(
        LOGIN_URL,
        json={"email": "ratelimit_login@example.com", "password": "password123"},
    )
    assert resp.status_code == 429
