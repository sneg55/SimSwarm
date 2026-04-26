import pytest


@pytest.mark.asyncio
async def test_export_pdf_returns_pdf(client, auth_headers, db_session):
    from saas.jobs.models import SimulationJob, JobStatus

    job = SimulationJob(
        user_id=auth_headers["_user_id"],
        seed_text="test",
        goal="test",
        tier="small",
        credits_charged=30,
        status=JobStatus.COMPLETED,
        result_report="# Test Report\n\nSome content here.",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/api/jobs/{job.id}/export/pdf", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
