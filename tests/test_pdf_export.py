"""Tests for PDF export endpoint."""
from unittest.mock import patch, MagicMock

from saas.jobs.models import SimulationJob, JobStatus


def _mock_delay():
    mock_task = MagicMock()
    mock_task.id = "celery-mock-id"
    return patch("saas.jobs.api.run_simulation_task.delay", return_value=mock_task)


async def _create_job(client, auth_headers, funded_user, seeded_routing):
    """Helper: create a job and return its id."""
    with _mock_delay():
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Some seed text for testing.",
                "goal": "Test the export endpoint",
                "tier": "small",
            },
        )
    assert resp.status_code == 201
    return resp.json()["id"]


async def test_export_pdf_requires_auth(client):
    """Unauthenticated request should return 401."""
    resp = await client.get("/api/jobs/1/export/pdf")
    assert resp.status_code == 401


async def test_export_pdf_not_found(client, auth_headers):
    """Non-existent job should return 404."""
    resp = await client.get("/api/jobs/99999/export/pdf", headers=auth_headers)
    assert resp.status_code == 404


async def test_export_pdf_no_report_returns_400(client, auth_headers, funded_user, seeded_routing, db_session):
    """Job without a result_report should return 400."""
    job_id = await _create_job(client, auth_headers, funded_user, seeded_routing)
    # Job has no result_report yet
    resp = await client.get(f"/api/jobs/{job_id}/export/pdf", headers=auth_headers)
    assert resp.status_code == 400
    assert "No report available" in resp.json()["detail"]


async def test_export_pdf_returns_pdf(client, auth_headers, funded_user, seeded_routing, db_session):
    """Completed job with a report should return a valid PDF binary."""
    job_id = await _create_job(client, auth_headers, funded_user, seeded_routing)

    # Directly set result_report on the job
    job = await db_session.get(SimulationJob, job_id)
    job.result_report = "# Test Report\n\n## Summary\n\nThis is a **test** report.\n\n- Point one\n- Point two"
    job.status = JobStatus.COMPLETED
    await db_session.commit()

    resp = await client.get(f"/api/jobs/{job_id}/export/pdf", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert f"simulation-{job_id}.pdf" in resp.headers["content-disposition"]

    # Verify it's a real PDF (starts with PDF magic bytes)
    content = resp.content
    assert content[:4] == b"%PDF"


async def test_export_pdf_forbidden_for_other_user(client, db_engine, auth_headers, funded_user, seeded_routing, db_session):
    """Another user must not be able to download another user's PDF."""
    from httpx import ASGITransport, AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from saas.main import create_app
    from saas.database import get_session
    from tests.conftest import test_settings

    job_id = await _create_job(client, auth_headers, funded_user, seeded_routing)
    job = await db_session.get(SimulationJob, job_id)
    job.result_report = "# Report"
    job.status = JobStatus.COMPLETED
    await db_session.commit()

    # Register a second user using the same app/db
    app = create_app(test_settings)
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        reg = await ac.post(
            "/api/auth/register",
            json={"email": "other@example.com", "password": "otherpass123"},
        )
        other_token = reg.json()["token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}

        resp = await ac.get(f"/api/jobs/{job_id}/export/pdf", headers=other_headers)
        assert resp.status_code == 403
