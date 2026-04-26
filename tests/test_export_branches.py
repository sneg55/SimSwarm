"""Coverage for saas.jobs.export branches."""
from saas.jobs.models import SimulationJob, JobStatus
from saas.jobs.export import markdown_to_pdf


async def test_pdf_not_found(client, auth_headers):
    resp = await client.get("/api/jobs/9999/export/pdf", headers=auth_headers)
    assert resp.status_code == 404


async def test_pdf_forbidden(client, auth_headers, db_session):
    job = SimulationJob(
        user_id="other", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED, result_report="r",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.get(f"/api/jobs/{job.id}/export/pdf", headers=auth_headers)
    assert resp.status_code == 403


async def test_pdf_no_report(client, auth_headers, db_session):
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.RUNNING,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.get(f"/api/jobs/{job.id}/export/pdf", headers=auth_headers)
    assert resp.status_code == 400


def test_markdown_to_pdf_covers_all_line_types():
    md = (
        "# Top Heading\n"
        "## Sub Heading\n"
        "\n"
        "Regular paragraph with **bold** text and an <angle> bracket and & amp.\n"
        "> A quote line with > entities\n"
        "- Bullet item with **bold**\n"
    )
    data = markdown_to_pdf(md, "My Title")
    assert data.startswith(b"%PDF")
    assert len(data) > 100
