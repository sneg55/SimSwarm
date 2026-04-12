"""Tests for retry / enrich-retry / graph endpoints."""
from unittest.mock import patch, MagicMock

from saas.jobs.models import SimulationJob, JobStatus


def _mock_delay():
    mock_task = MagicMock()
    mock_task.id = "celery-mock-id"
    return patch("saas.jobs.api.run_simulation_task.delay", return_value=mock_task)


async def test_retry_job_not_found(client, auth_headers):
    resp = await client.post("/api/jobs/99999/retry", headers=auth_headers)
    assert resp.status_code == 404


async def test_retry_job_forbidden(client, auth_headers, db_session):
    job = SimulationJob(
        user_id="other-user", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.FAILED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.post(f"/api/jobs/{job.id}/retry", headers=auth_headers)
    assert resp.status_code == 403


async def test_retry_job_wrong_status(client, auth_headers, db_session):
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.post(f"/api/jobs/{job.id}/retry", headers=auth_headers)
    assert resp.status_code == 400


async def test_retry_job_success(client, auth_headers, funded_user, seeded_routing, db_session):
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="original seed", goal="original goal",
        tier="small", credits_charged=30, status=JobStatus.FAILED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    with _mock_delay():
        resp = await client.post(f"/api/jobs/{job.id}/retry", headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["seed_text"] == "original seed"
    assert data["tier"] == "small"


async def test_enrich_retry_not_found(client, auth_headers):
    resp = await client.post("/api/jobs/9999/enrich-retry", headers=auth_headers)
    assert resp.status_code == 404


async def test_enrich_retry_forbidden(client, auth_headers, db_session):
    job = SimulationJob(
        user_id="other-user", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.post(f"/api/jobs/{job.id}/enrich-retry", headers=auth_headers)
    assert resp.status_code == 403


async def test_enrich_retry_happy(client, auth_headers, db_session):
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    with patch("saas.jobs.tasks.enrich_retry_task.delay") as mock_delay:
        mock_delay.return_value = MagicMock(id="tid")
        resp = await client.post(f"/api/jobs/{job.id}/enrich-retry", headers=auth_headers)
    assert resp.status_code == 202
    assert resp.json() == {"status": "retrying"}


async def test_get_job_graph_not_found(client, auth_headers):
    resp = await client.get("/api/jobs/9999/graph", headers=auth_headers)
    assert resp.status_code == 404


async def test_get_job_graph_forbidden(client, auth_headers, db_session):
    job = SimulationJob(
        user_id="other-user", seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED, result_graph='{"nodes":[]}',
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
    assert resp.status_code == 403


async def test_get_job_graph_no_data(client, auth_headers, db_session):
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
    assert resp.status_code == 404


async def test_get_job_graph_invalid_json(client, auth_headers, db_session):
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED, result_graph="not-json{",
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
    assert resp.status_code == 500


async def test_get_job_graph_success(client, auth_headers, db_session):
    import json
    graph = json.dumps({"nodes": [{"uuid": "n1", "name": "A"}], "edges": []})
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED, result_graph=graph,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.get(f"/api/jobs/{job.id}/graph", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["nodes"][0]["name"] == "A"


async def test_get_sim_data_not_found(client, auth_headers):
    resp = await client.get("/api/jobs/9999/sim-data", headers=auth_headers)
    assert resp.status_code == 404


async def test_get_sim_data_unavailable(client, auth_headers, db_session):
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED, sim_data_available=False,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.get(f"/api/jobs/{job.id}/sim-data", headers=auth_headers)
    assert resp.status_code == 404


async def test_get_sim_data_minio_not_configured(client, auth_headers, db_session):
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="x", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED, sim_data_available=True,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    resp = await client.get(f"/api/jobs/{job.id}/sim-data", headers=auth_headers)
    assert resp.status_code == 404
