from unittest.mock import patch, MagicMock


def _mock_delay():
    mock_task = MagicMock()
    mock_task.id = "celery-mock-id"
    return patch("saas.jobs.api.run_simulation_task.delay", return_value=mock_task)


async def test_sim_data_returns_404_when_not_available(client, auth_headers, funded_user, seeded_routing):
    """GET /api/jobs/{id}/sim-data returns 404 when sim_data_available is false."""
    with _mock_delay():
        create_resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Test seed text for simulation.",
                "goal": "Test goal",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    job_id = create_resp.json()["id"]

    response = await client.get(f"/api/jobs/{job_id}/sim-data", headers=auth_headers)
    assert response.status_code == 404


async def test_sim_data_returns_404_for_nonexistent_job(client, auth_headers):
    """GET /api/jobs/99999/sim-data returns 404."""
    response = await client.get("/api/jobs/99999/sim-data", headers=auth_headers)
    assert response.status_code == 404


async def test_sim_data_requires_auth(client):
    """GET /api/jobs/1/sim-data returns 401 without auth."""
    response = await client.get("/api/jobs/1/sim-data")
    assert response.status_code == 401
