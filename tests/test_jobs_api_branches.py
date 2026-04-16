"""Additional coverage for saas.jobs.api branches - basic CRUD."""
from unittest.mock import patch, MagicMock

from saas.jobs.models import SimulationJob, JobStatus


def _mock_delay():
    mock_task = MagicMock()
    mock_task.id = "celery-mock-id"
    return patch("saas.jobs.api.run_simulation_task.delay", return_value=mock_task)


async def test_get_job_forbidden_for_other_user(client, auth_headers, db_session):
    job = SimulationJob(
        user_id="other-user", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.PENDING,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.get(f"/api/jobs/{job.id}", headers=auth_headers)
    assert resp.status_code == 403


async def test_delete_job_happy(client, auth_headers, db_session):
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.delete(f"/api/jobs/{job.id}", headers=auth_headers)
    assert resp.status_code == 204


async def test_delete_job_not_found(client, auth_headers):
    resp = await client.delete("/api/jobs/99999", headers=auth_headers)
    assert resp.status_code == 404


async def test_delete_job_forbidden(client, auth_headers, db_session):
    job = SimulationJob(
        user_id="other-user", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.delete(f"/api/jobs/{job.id}", headers=auth_headers)
    assert resp.status_code == 403


async def test_create_job_no_routing(client, auth_headers, funded_user):
    resp = await client.post(
        "/api/jobs", headers=auth_headers,
        json={"seed_text": "seed", "goal": "goal", "tier": "small", "forecast_days": 30},
    )
    assert resp.status_code == 500


async def test_create_job_insufficient_credits(client, auth_headers, seeded_routing):
    resp = await client.post(
        "/api/jobs", headers=auth_headers,
        json={"seed_text": "seed", "goal": "goal", "tier": "small", "forecast_days": 30},
    )
    assert resp.status_code == 402


async def test_create_job_dispatch_failure(client, auth_headers, funded_user, seeded_routing):
    with patch("saas.jobs.api.run_simulation_task.delay", side_effect=RuntimeError("fail")):
        resp = await client.post(
            "/api/jobs", headers=auth_headers,
            json={"seed_text": "seed", "goal": "goal", "tier": "small", "forecast_days": 30},
        )
    assert resp.status_code == 500


async def test_list_jobs_pagination_hides_superseded(client, auth_headers, db_session):
    old = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="old", goal="old", tier="small",
        credits_charged=30, status=JobStatus.FAILED,
    )
    db_session.add(old)
    await db_session.commit()
    await db_session.refresh(old)

    new = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="new", goal="new", tier="small",
        credits_charged=30, status=JobStatus.PENDING, retry_of=old.id,
    )
    db_session.add(new)
    await db_session.commit()

    resp = await client.get("/api/jobs", headers=auth_headers)
    assert resp.status_code == 200
    ids = [j["id"] for j in resp.json()["jobs"]]
    assert old.id not in ids
    assert new.id in ids
