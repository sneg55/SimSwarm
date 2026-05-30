"""
End-to-end integration tests for job creation and lifecycle.

Covers full job lifecycle with funded user, ownership isolation, and
forecast_days validation.
"""
from __future__ import annotations

from tests.test_e2e_helpers import mock_celery_delay


# ---------------------------------------------------------------------------
# Full job lifecycle (with funded user and model routing)
# ---------------------------------------------------------------------------


async def test_full_job_lifecycle(client, auth_headers, funded_user, seeded_routing):
    """Create job, retrieve it, and list it."""
    with mock_celery_delay():
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Breaking news about AI regulation in the EU.",
                "goal": "Predict tech industry response over 30 days",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert resp.status_code == 201
    job = resp.json()
    assert job["status"].upper() == "PENDING"
    assert job["credits_charged"] == 0
    job_id = job["id"]

    # Get job by ID
    get_resp = await client.get(f"/api/jobs/{job_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["goal"] == "Predict tech industry response over 30 days"

    # List jobs — should contain our new job
    list_resp = await client.get("/api/jobs", headers=auth_headers)
    assert list_resp.status_code == 200
    job_ids = [j["id"] for j in list_resp.json()["jobs"]]
    assert job_id in job_ids


# ---------------------------------------------------------------------------
# Job ownership isolation between users
# ---------------------------------------------------------------------------


async def test_job_ownership_isolation(client, seeded_routing):
    """User2 cannot see or access jobs created by User1."""
    # Register two users
    r1 = await client.post(
        "/api/auth/register",
        json={"email": "user1@test.com", "password": "testpass123"},
    )
    r2 = await client.post(
        "/api/auth/register",
        json={"email": "user2@test.com", "password": "testpass123"},
    )
    h1 = {"Authorization": f"Bearer {r1.json()['token']}"}
    h2 = {"Authorization": f"Bearer {r2.json()['token']}"}

    # Create a job as user1
    with mock_celery_delay():
        job_resp = await client.post(
            "/api/jobs",
            headers=h1,
            json={
                "seed_text": "User1 seed",
                "goal": "User1 goal",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert job_resp.status_code == 201
    job_id = job_resp.json()["id"]

    # User2 job list should be empty
    jobs2 = await client.get("/api/jobs", headers=h2)
    assert jobs2.status_code == 200
    assert jobs2.json()["jobs"] == []
    assert jobs2.json()["total"] == 0

    # User2 cannot retrieve user1's job
    get_resp = await client.get(f"/api/jobs/{job_id}", headers=h2)
    assert get_resp.status_code == 403

    # User1 can still see their own job
    jobs1 = await client.get("/api/jobs", headers=h1)
    assert len(jobs1.json()["jobs"]) == 1
    assert jobs1.json()["jobs"][0]["id"] == job_id


# ---------------------------------------------------------------------------
# All three job tiers charge correct credits
# ---------------------------------------------------------------------------


async def test_all_tiers_accepted(client, auth_headers, funded_user, seeded_routing):
    """All three job tiers are accepted and create jobs successfully."""
    with mock_celery_delay():
        for tier in ("small", "medium", "large"):
            resp = await client.post(
                "/api/jobs",
                headers=auth_headers,
                json={
                    "seed_text": f"Seed for {tier} simulation.",
                    "goal": "Test goal",
                    "tier": tier,
                    "forecast_days": 30,
                },
            )
            assert resp.status_code == 201, f"tier={tier} got {resp.status_code}: {resp.text}"
            assert resp.json()["credits_charged"] == 0
            assert resp.json()["tier"] == tier


# ---------------------------------------------------------------------------
# forecast_days is required on JobCreate
# ---------------------------------------------------------------------------


async def test_create_job_rejects_missing_forecast_days(client, funded_user, auth_headers):
    """POST /api/jobs without forecast_days returns 422 — field is required."""
    resp = await client.post(
        "/api/jobs",
        json={"seed_text": "seed", "goal": "goal", "tier": "small"},  # no forecast_days
        headers=auth_headers,
    )
    assert resp.status_code == 422
