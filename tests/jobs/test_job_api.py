"""Tests for the job API response surface."""
from __future__ import annotations


async def test_job_response_includes_forecast_days(
    client, auth_headers, db_session
):
    from saas.jobs.models import SimulationJob

    user_id = auth_headers["_user_id"]
    job = SimulationJob(
        user_id=user_id,
        seed_text="seed",
        goal="goal",
        tier="small",
        credits_charged=10,
        status="COMPLETED",
        forecast_days=90,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    headers = {"Authorization": auth_headers["Authorization"]}
    resp = await client.get(f"/api/jobs/{job.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["forecast_days"] == 90
