"""Coverage for uncovered branches in saas.jobs.api_draft."""
from unittest.mock import patch, MagicMock, AsyncMock

from saas.jobs.models import SimulationJob, JobStatus


SEED = "A" * 600


def _mock_temporal_draft():
    fake_handle = MagicMock()
    fake_handle.id = "sim-draft-id"
    fake_handle.result_run_id = "run-draft"
    fake_client = AsyncMock()
    fake_client.start_workflow = AsyncMock(return_value=fake_handle)
    return patch("saas.jobs.api_draft.get_temporal_client", new=AsyncMock(return_value=fake_client))


async def test_launch_nonexistent_draft(client, auth_headers):
    resp = await client.post("/api/jobs/draft/99999/launch", headers=auth_headers)
    assert resp.status_code == 404


async def test_launch_missing_routing(client, auth_headers, funded_user, db_session):
    """No model_routing entries but draft complete -> 500."""
    create = await client.post(
        "/api/jobs/draft", json={"seed_text": SEED}, headers=auth_headers,
    )
    did = create.json()["id"]
    await client.patch(
        f"/api/jobs/draft/{did}",
        json={"goal": "g", "tier": "small", "forecast_days": 30},
        headers=auth_headers,
    )
    resp = await client.post(f"/api/jobs/draft/{did}/launch", headers=auth_headers)
    assert resp.status_code == 500


async def test_launch_dispatch_failure(client, auth_headers, funded_user, seeded_routing):
    create = await client.post(
        "/api/jobs/draft", json={"seed_text": SEED}, headers=auth_headers,
    )
    did = create.json()["id"]
    await client.patch(
        f"/api/jobs/draft/{did}",
        json={"goal": "g", "tier": "small", "forecast_days": 30},
        headers=auth_headers,
    )
    with patch("saas.jobs.api_draft.get_temporal_client", new=AsyncMock(side_effect=RuntimeError("boom"))):
        resp = await client.post(f"/api/jobs/draft/{did}/launch", headers=auth_headers)
    assert resp.status_code == 500


async def test_update_draft_all_fields(client, auth_headers):
    create = await client.post(
        "/api/jobs/draft", json={"seed_text": SEED}, headers=auth_headers,
    )
    did = create.json()["id"]

    resp = await client.patch(
        f"/api/jobs/draft/{did}",
        json={
            "seed_text": "B" * 600,
            "goal": "updated goal",
            "tier": "medium",
            "enrich_web": False,
            "forecast_days": 45,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    d = resp.json()
    assert d["seed_text"].startswith("B")
    assert d["goal"] == "updated goal"
    assert d["tier"] == "medium"


async def test_launch_empty_seed_text(client, auth_headers, funded_user, seeded_routing, db_session):
    """Whitespace-only seed_text counts as missing."""
    job = SimulationJob(
        user_id=auth_headers["_user_id"], seed_text="    ", goal="g", tier="small",
        credits_charged=0, status=JobStatus.DRAFT,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.post(f"/api/jobs/draft/{job.id}/launch", headers=auth_headers)
    assert resp.status_code == 422
    assert "seed_text" in resp.json()["detail"]


async def test_launch_success_dispatches(client, auth_headers, funded_user, seeded_routing):
    """Successful launch dispatches workflow and transitions to PENDING."""
    create = await client.post(
        "/api/jobs/draft",
        json={"seed_text": SEED, "goal": "g", "tier": "small", "forecast_days": 7},
        headers=auth_headers,
    )
    did = create.json()["id"]

    with _mock_temporal_draft():
        resp = await client.post(f"/api/jobs/draft/{did}/launch", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "PENDING"
