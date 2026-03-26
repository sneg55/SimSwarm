import pytest


async def test_create_job(client, funded_user):
    response = await client.post(
        "/api/jobs",
        json={
            "user_id": "user-123",
            "seed_text": "Breaking news: markets are volatile.",
            "goal": "Predict market sentiment over 7 days",
            "tier": "small",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == "user-123"
    assert data["tier"] == "small"
    assert data["credits_charged"] == 30
    assert data["status"] == "pending"
    assert "id" in data


async def test_create_job_invalid_tier(client):
    response = await client.post(
        "/api/jobs",
        json={
            "user_id": "user-123",
            "seed_text": "Test",
            "goal": "Test",
            "tier": "mega",
        },
    )
    assert response.status_code == 422


async def test_create_job_seed_too_long(client, funded_user):
    response = await client.post(
        "/api/jobs",
        json={
            "user_id": "user-123",
            "seed_text": "x" * 50_001,
            "goal": "Test",
            "tier": "small",
        },
    )
    assert response.status_code == 400
    assert "50000" in response.json()["detail"]


async def test_get_job_status(client, funded_user):
    create_resp = await client.post(
        "/api/jobs",
        json={
            "user_id": "user-123",
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "medium",
        },
    )
    job_id = create_resp.json()["id"]

    response = await client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["status"] == "pending"
    assert data["credits_charged"] == 90


async def test_get_job_not_found(client):
    response = await client.get("/api/jobs/99999")
    assert response.status_code == 404


async def test_list_user_jobs(client, funded_user):
    for _ in range(2):
        await client.post(
            "/api/jobs",
            json={
                "user_id": "user-456",
                "seed_text": "Test",
                "goal": "Test",
                "tier": "small",
            },
        )

    response = await client.get("/api/jobs", params={"user_id": "user-456"})
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(j["user_id"] == "user-456" for j in data)
