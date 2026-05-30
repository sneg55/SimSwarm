from unittest.mock import patch, AsyncMock
from sqlalchemy import select, func
from saas.jobs.models import SimulationJob


async def test_missing_routing_creates_no_job(client, auth_headers, funded_user, db_session):
    """If model routing is not configured, the job must not be created."""
    resp = await client.post(
        "/api/jobs",
        headers=auth_headers,
        json={
            "seed_text": "Test seed text.",
            "goal": "Test",
            "tier": "small",
            "forecast_days": 30,
        },
    )
    assert resp.status_code == 500
    assert "routing" in resp.json()["detail"].lower()

    # DB invariant: no SimulationJob row must have been persisted.
    count = (await db_session.execute(
        select(func.count()).select_from(SimulationJob).where(
            SimulationJob.user_id == auth_headers["_user_id"]
        )
    )).scalar_one()
    assert count == 0, f"Expected 0 job rows, found {count}"


async def test_dispatch_failure_rolls_back_job_row(client, auth_headers, funded_user, seeded_routing, db_session):
    """If Temporal dispatch fails, the job row must not be persisted."""
    with patch("saas.jobs.api.get_temporal_client", new=AsyncMock(side_effect=Exception("temporal down"))):
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Test seed text.",
                "goal": "Test",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert resp.status_code == 500

    # DB invariant: the job row must have been rolled back.
    count = (await db_session.execute(
        select(func.count()).select_from(SimulationJob).where(
            SimulationJob.user_id == auth_headers["_user_id"]
        )
    )).scalar_one()
    assert count == 0, f"Expected 0 job rows after rollback, found {count}"
