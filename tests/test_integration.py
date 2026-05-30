"""
Integration test: create a job via API, verify it's persisted,
query it back, and verify the full flow works.
"""
from unittest.mock import patch, MagicMock, AsyncMock


def _mock_delay():
    fake_handle = MagicMock()
    fake_handle.id = "sim-mock-id"
    fake_handle.result_run_id = "run-mock"
    fake_client = AsyncMock()
    fake_client.start_workflow = AsyncMock(return_value=fake_handle)
    return patch("saas.jobs.api.get_temporal_client", new=AsyncMock(return_value=fake_client))


async def test_full_job_lifecycle(client, auth_headers, funded_user, seeded_routing):
    # 1. Health check
    health = await client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    # 2. Create a small job
    with _mock_delay():
        create_resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Breaking news: AI regulation passed in EU parliament.",
                "goal": "Predict tech industry response over 14 days",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert create_resp.status_code == 201
    job = create_resp.json()
    assert job["credits_charged"] == 0
    assert job["status"] == "PENDING"
    job_id = job["id"]

    # 3. Retrieve the job
    get_resp = await client.get(f"/api/jobs/{job_id}", headers=auth_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["goal"] == "Predict tech industry response over 14 days"

    # 4. List jobs for user
    list_resp = await client.get("/api/jobs", headers=auth_headers)
    assert list_resp.status_code == 200
    jobs = list_resp.json()["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["id"] == job_id


async def test_create_jobs_all_tiers(client, auth_headers, funded_user, seeded_routing):
    """Verify all three tiers are accepted and create jobs successfully."""
    with _mock_delay():
        for tier in ("small", "medium", "large"):
            resp = await client.post(
                "/api/jobs",
                headers=auth_headers,
                json={
                    "seed_text": f"Seed for {tier} simulation",
                    "goal": "Test goal",
                    "tier": tier,
                    "forecast_days": 30,
                },
            )
            assert resp.status_code == 201
            assert resp.json()["credits_charged"] == 0
            assert resp.json()["tier"] == tier
