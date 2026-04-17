"""Tests that GET /api/jobs/{id} returns markets_config."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest


@pytest.mark.asyncio
async def test_get_job_returns_markets_config(client, auth_headers, db_session):
    from saas.jobs.models import SimulationJob, JobStatus

    markets = [
        {"question": "Will X?", "initial_price_yes": 0.55, "rationale": "because"}
    ]
    user_id = auth_headers["_user_id"]
    job = SimulationJob(
        user_id=user_id,
        seed_text="s", goal="g", tier="small",
        credits_charged=30, status=JobStatus.COMPLETED,
        created_at=datetime.now(timezone.utc),
        markets_config=markets,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    headers = {k: v for k, v in auth_headers.items() if not k.startswith("_")}
    resp = await client.get(f"/api/jobs/{job.id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["markets_config"] == markets


@pytest.mark.asyncio
async def test_get_job_markets_config_null_when_unset(client, auth_headers, db_session):
    from saas.jobs.models import SimulationJob, JobStatus

    user_id = auth_headers["_user_id"]
    job = SimulationJob(
        user_id=user_id,
        seed_text="s", goal="g", tier="small",
        credits_charged=30, status=JobStatus.PENDING,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    headers = {k: v for k, v in auth_headers.items() if not k.startswith("_")}
    resp = await client.get(f"/api/jobs/{job.id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["markets_config"] is None
