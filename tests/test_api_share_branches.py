"""Coverage for saas.jobs.api_share branches."""
from saas.jobs.models import SimulationJob, JobStatus


async def test_share_not_found(client, auth_headers):
    resp = await client.post("/api/jobs/9999/share", headers=auth_headers)
    assert resp.status_code == 404


async def test_share_forbidden_other_user(client, auth_headers, db_session):
    job = SimulationJob(
        user_id="other", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.post(f"/api/jobs/{job.id}/share", headers=auth_headers)
    assert resp.status_code == 403


async def test_share_only_completed(client, auth_headers, db_session):
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.RUNNING,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.post(f"/api/jobs/{job.id}/share", headers=auth_headers)
    assert resp.status_code == 400


async def test_share_reuses_existing_token(client, auth_headers, db_session):
    """Second call returns same token, doesn't regenerate."""
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    r1 = await client.post(f"/api/jobs/{job.id}/share", headers=auth_headers)
    r2 = await client.post(f"/api/jobs/{job.id}/share", headers=auth_headers)
    assert r1.json()["share_token"] == r2.json()["share_token"]


async def test_revoke_not_found(client, auth_headers):
    resp = await client.delete("/api/jobs/9999/share", headers=auth_headers)
    assert resp.status_code == 404


async def test_revoke_forbidden(client, auth_headers, db_session):
    job = SimulationJob(
        user_id="other", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED, share_token="existing",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.delete(f"/api/jobs/{job.id}/share", headers=auth_headers)
    assert resp.status_code == 403
