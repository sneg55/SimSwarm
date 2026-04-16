"""
End-to-end integration tests for auth, billing, and validation flows.

Job-lifecycle tests live in test_e2e_jobs.py; shared helpers live in
test_e2e_helpers.py.
"""
from __future__ import annotations

from tests.test_e2e_helpers import mock_celery_delay


# ---------------------------------------------------------------------------
# Test 1: Registration → Login → Balance check
# ---------------------------------------------------------------------------


async def test_register_login_balance_flow(client):
    """Full registration and login flow with balance and jobs check."""
    # Register
    reg = await client.post(
        "/api/auth/register",
        json={"email": "e2e@test.com", "password": "testpass123"},
    )
    assert reg.status_code == 201
    reg_data = reg.json()
    assert "token" in reg_data
    assert reg_data["user"]["email"] == "e2e@test.com"
    token = reg_data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Login with same credentials
    login = await client.post(
        "/api/auth/login",
        json={"email": "e2e@test.com", "password": "testpass123"},
    )
    assert login.status_code == 200
    login_data = login.json()
    assert "token" in login_data
    assert login_data["user"]["email"] == "e2e@test.com"

    # Check balance (should be 0 for new user)
    bal = await client.get("/api/billing/balance", headers=headers)
    assert bal.status_code == 200
    assert bal.json()["balance"] == 0

    # List jobs (should be empty)
    jobs = await client.get("/api/jobs", headers=headers)
    assert jobs.status_code == 200
    assert jobs.json()["jobs"] == []
    assert jobs.json()["total"] == 0


# ---------------------------------------------------------------------------
# Test 2: Job creation requires credits (402 gate)
# ---------------------------------------------------------------------------


async def test_job_requires_credits(client, seeded_routing):
    """User with zero credits cannot create a job — gets 402."""
    reg = await client.post(
        "/api/auth/register",
        json={"email": "e2e-credits@test.com", "password": "testpass123"},
    )
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}

    resp = await client.post(
        "/api/jobs",
        headers=headers,
        json={
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "small",
            "forecast_days": 30,
        },
    )
    assert resp.status_code == 402
    assert "credits" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 3: Auth protection on all protected endpoints
# ---------------------------------------------------------------------------


async def test_endpoints_require_auth(client):
    """All protected endpoints return 401 when no token is provided."""
    # Jobs endpoints
    assert (await client.get("/api/jobs")).status_code == 401
    assert (
        await client.post(
            "/api/jobs",
            json={"seed_text": "x", "goal": "x", "tier": "small", "forecast_days": 30},
        )
    ).status_code == 401
    assert (await client.get("/api/jobs/1")).status_code == 401

    # Billing endpoints
    assert (await client.get("/api/billing/balance")).status_code == 401
    assert (await client.get("/api/billing/history")).status_code == 401
    assert (
        await client.post("/api/billing/purchase", json={"pack_id": "starter"})
    ).status_code == 401

    # Health does not require auth
    assert (await client.get("/api/health")).status_code == 200

    # Auth endpoints are public
    register_resp = await client.post(
        "/api/auth/register",
        json={"email": "noauth@test.com", "password": "testpass123"},
    )
    assert register_resp.status_code == 201


# ---------------------------------------------------------------------------
# Test 4: Seed text validation
# ---------------------------------------------------------------------------


async def test_seed_text_validation(client, auth_headers, funded_user, seeded_routing):
    """Validate seed_text constraints: empty → 422, too long → 400."""
    # Empty seed text
    resp = await client.post(
        "/api/jobs",
        headers=auth_headers,
        json={"seed_text": "", "goal": "Test", "tier": "small", "forecast_days": 30},
    )
    assert resp.status_code == 422

    # Seed too long (over 50 000 characters)
    with mock_celery_delay():
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "x" * 50_001,
                "goal": "Test",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert resp.status_code == 400
    assert "50000" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Test 5: Credit ledger integrity
# ---------------------------------------------------------------------------


async def test_credit_ledger_integrity(client, db_session, seeded_routing):
    """Verify the ledger balance and history stay consistent after a job charge."""
    reg = await client.post(
        "/api/auth/register",
        json={"email": "ledger@test.com", "password": "testpass123"},
    )
    assert reg.status_code == 201
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}
    user_id = str(reg.json()["user"]["id"])

    # Fund via ledger
    from saas.billing.ledger import CreditLedger
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id, 100, "Test credits")
    await db_session.commit()

    # Confirm balance
    bal = await client.get("/api/billing/balance", headers=headers)
    assert bal.status_code == 200
    assert bal.json()["balance"] == 100

    # Create a small job (costs 30 credits)
    with mock_celery_delay():
        job_resp = await client.post(
            "/api/jobs",
            headers=headers,
            json={
                "seed_text": "Test seed",
                "goal": "Test goal",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert job_resp.status_code == 201

    # Balance should now be 70
    bal = await client.get("/api/billing/balance", headers=headers)
    assert bal.status_code == 200
    assert bal.json()["balance"] == 70

    # History should have exactly 2 entries: credit then debit
    hist = await client.get("/api/billing/history", headers=headers)
    assert hist.status_code == 200
    entries = hist.json()
    assert len(entries) == 2
    assert entries[0]["amount"] == 100   # credit
    assert entries[1]["amount"] == -30   # debit for job


# ---------------------------------------------------------------------------
# Test 6: Demo / health endpoints
# ---------------------------------------------------------------------------


async def test_demo_pages_served(client):
    """Health endpoint is reachable and returns ok status."""
    health = await client.get("/api/health")
    assert health.status_code == 200
    data = health.json()
    assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# Test 7: Duplicate registration returns 409
# ---------------------------------------------------------------------------


async def test_duplicate_registration_rejected(client):
    """Registering the same email twice returns 409 Conflict."""
    payload = {"email": "dup@test.com", "password": "testpass123"}
    r1 = await client.post("/api/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/auth/register", json=payload)
    assert r2.status_code == 409
