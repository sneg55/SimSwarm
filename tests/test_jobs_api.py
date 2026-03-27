import pytest
from unittest.mock import patch, MagicMock


def _mock_delay():
    mock_task = MagicMock()
    mock_task.id = "celery-mock-id"
    return patch("saas.api.jobs.run_simulation_task.delay", return_value=mock_task)


async def test_create_job(client, auth_headers, funded_user, seeded_routing):
    with _mock_delay():
        response = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Breaking news: markets are volatile.",
                "goal": "Predict market sentiment over 7 days",
                "tier": "small",
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
                },
            )

    response = await client.get("/api/jobs", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(j["user_id"] == auth_headers["_user_id"] for j in data)


async def test_unauthenticated_request_returns_401(client):
    response = await client.post(
        "/api/jobs",
        json={
            "seed_text": "Test",
            "goal": "Test",
            "tier": "small",
        },
    )
    assert response.status_code == 401
