"""
End-to-end integration test: create a job via API, verify it's persisted,
query it back, and verify the full flow works.
"""
from unittest.mock import patch, MagicMock


def _mock_delay():
    mock_task = MagicMock()
    mock_task.id = "celery-mock-id"
    return patch("saas.api.jobs.run_simulation_task.delay", return_value=mock_task)


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
            },
        )
    assert create_resp.status_code == 201
    job = create_resp.json()
    assert job["credits_charged"] == 30
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
    """Verify credit charging for all three tiers."""
    expected = {"small": 30, "medium": 90, "large": 300}

    with _mock_delay():
        for tier, credits in expected.items():
            resp = await client.post(
                "/api/jobs",
                headers=auth_headers,
                json={
                    "seed_text": f"Seed for {tier} simulation",
                    "goal": "Test goal",
                    "tier": tier,
                },
            )
            assert resp.status_code == 201
            assert resp.json()["credits_charged"] == credits
            assert resp.json()["tier"] == tier
