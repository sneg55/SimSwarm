"""Coverage for saas.jobs.progress SSE streaming."""
from saas.jobs.models import SimulationJob, JobStatus


async def test_progress_not_found(client, auth_headers):
    resp = await client.get("/api/jobs/9999/progress", headers=auth_headers)
    assert resp.status_code == 404


async def test_progress_forbidden(client, auth_headers, db_session):
    job = SimulationJob(
        user_id="other", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/api/jobs/{job.id}/progress", headers=auth_headers)
    assert resp.status_code == 403
