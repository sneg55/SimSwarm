import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def _mock_temporal():
    fake_handle = MagicMock()
    fake_handle.id = "sim-mock-id"
    fake_handle.result_run_id = "run-mock"
    fake_client = AsyncMock()
    fake_client.start_workflow = AsyncMock(return_value=fake_handle)
    return patch("saas.jobs.api.get_temporal_client", new=AsyncMock(return_value=fake_client))


# Keep alias so callers don't need updating
_mock_delay = _mock_temporal


async def test_create_job(client, auth_headers, funded_user, seeded_routing):
    with _mock_delay():
        response = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Breaking news: markets are volatile.",
                "goal": "Predict market sentiment over 7 days",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == auth_headers["_user_id"]
    assert data["tier"] == "small"
    assert data["credits_charged"] == 30
    assert data["status"] == "PENDING"
    assert "id" in data


async def test_create_job_invalid_tier(client, auth_headers):
    response = await client.post(
        "/api/jobs",
        headers=auth_headers,
        json={
            "seed_text": "Test",
            "goal": "Test",
            "tier": "mega",
            "forecast_days": 30,
        },
    )
    assert response.status_code == 422


async def test_create_job_seed_too_long(client, auth_headers, funded_user, seeded_routing):
    with _mock_delay():
        response = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "x" * 50_001,
                "goal": "Test",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert response.status_code == 400
    assert "50000" in response.json()["detail"]


async def test_get_job_status(client, auth_headers, funded_user, seeded_routing):
    with _mock_delay():
        create_resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Test seed",
                "goal": "Test goal",
                "tier": "medium",
                "forecast_days": 30,
            },
        )
    job_id = create_resp.json()["id"]

    response = await client.get(f"/api/jobs/{job_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["status"] == "PENDING"
    assert data["credits_charged"] == 90


async def test_get_job_not_found(client, auth_headers):
    response = await client.get("/api/jobs/99999", headers=auth_headers)
    assert response.status_code == 404


async def test_list_user_jobs(client, auth_headers, funded_user, seeded_routing):
    with _mock_delay():
        for _ in range(2):
            await client.post(
                "/api/jobs",
                headers=auth_headers,
                json={
                    "seed_text": "Test",
                    "goal": "Test",
                    "tier": "small",
                    "forecast_days": 30,
                },
            )

    response = await client.get("/api/jobs", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert data["page"] == 1
    assert data["per_page"] == 10
    jobs = data["jobs"]
    assert len(jobs) == 2
    # JobSummary does not include user_id; verify other fields are present
    assert all("goal" in j for j in jobs)
    assert all("status" in j for j in jobs)


async def test_unauthenticated_request_returns_401(client):
    response = await client.post(
        "/api/jobs",
        json={
            "seed_text": "Test",
            "goal": "Test",
            "tier": "small",
            "forecast_days": 30,
        },
    )
    assert response.status_code == 401


async def test_create_job_with_forecast_days(client, auth_headers, funded_user, seeded_routing):
    with _mock_delay():
        response = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Breaking news: markets are volatile.",
                "goal": "Predict market sentiment",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert response.status_code == 201
    data = response.json()
    assert data["tier"] == "small"
    assert data["credits_charged"] == 30


@pytest.mark.asyncio
async def test_create_job_starts_temporal_workflow(
    client, auth_headers, funded_user, seeded_routing,
):
    """POST /jobs must start a Temporal workflow (not a Celery task)."""
    from unittest.mock import AsyncMock, patch

    fake_handle = AsyncMock()
    fake_handle.id = "sim-42"
    fake_handle.result_run_id = "run-abc"
    fake_client = AsyncMock()
    fake_client.start_workflow = AsyncMock(return_value=fake_handle)

    with patch(
        "saas.jobs.api.get_temporal_client",
        new=AsyncMock(return_value=fake_client),
    ):
        resp = await client.post(
            "/api/jobs",
            json={
                "seed_text": "x", "goal": "y",
                "tier": "small", "enrich_web": False,
                "forecast_days": 30,
            },
            headers=auth_headers,
        )
    assert resp.status_code == 201
    fake_client.start_workflow.assert_called_once()
    kwargs = fake_client.start_workflow.call_args.kwargs
    assert kwargs["id"].startswith("sim-")
    assert kwargs["task_queue"] == "sim-queue"
