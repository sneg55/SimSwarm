"""Integration tests for job dispatch lifecycle and credit recovery (#22).

These tests exercise the full job lifecycle (create -> status transitions -> refund)
against a real test SQLite database, verifying that credits are correctly debited,
refunded on failure, and that status transitions are properly persisted.
"""
from unittest.mock import patch, MagicMock, AsyncMock

from saas.jobs.models import SimulationJob, JobStatus


async def test_failed_job_gets_refund(client, auth_headers, funded_user, seeded_routing, db_session):
    """When a job fails, credits should be refunded."""
    # Create job
    fake_handle = MagicMock()
    fake_handle.id = "sim-mock-id"
    fake_handle.result_run_id = "run-mock"
    fake_client = AsyncMock()
    fake_client.start_workflow = AsyncMock(return_value=fake_handle)
    with patch("saas.jobs.api.get_temporal_client", new=AsyncMock(return_value=fake_client)):
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Test content for simulation.",
                "goal": "Test",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert resp.status_code == 201
    job_id = resp.json()["id"]

    # Check credits were deducted
    balance = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance.json()["balance"] == 10000 - 30

    # Simulate job failure by marking it failed + refunding (what the worker does)
    from saas.billing.ledger import CreditLedger

    # Mark failed via DB
    job = await db_session.get(SimulationJob, job_id)
    job.status = JobStatus.FAILED
    job.error_message = "Test failure"
    await db_session.commit()

    # Refund via ledger
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id=auth_headers["_user_id"], amount=30, description=f"Refund for job {job_id}")
    await db_session.commit()

    # Check balance restored
    balance = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance.json()["balance"] == 10000


async def test_duplicate_refund_creates_extra_credit(client, auth_headers, funded_user, seeded_routing, db_session):
    """Two refunds for the same job should both apply (idempotency is at webhook level, not refund level)."""
    from saas.billing.ledger import CreditLedger

    ledger = CreditLedger(db_session)
    uid = auth_headers["_user_id"]
    await ledger.credit(user_id=uid, amount=30, description="Refund 1")
    await ledger.credit(user_id=uid, amount=30, description="Refund 2")
    await db_session.commit()

    balance = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance.json()["balance"] == 10000 + 60


async def test_job_status_transitions(client, auth_headers, funded_user, seeded_routing, db_session):
    """Job goes through valid status transitions."""
    fake_handle2 = MagicMock()
    fake_handle2.id = "sim-mock-id-2"
    fake_handle2.result_run_id = "run-mock-2"
    fake_client2 = AsyncMock()
    fake_client2.start_workflow = AsyncMock(return_value=fake_handle2)
    with patch("saas.jobs.api.get_temporal_client", new=AsyncMock(return_value=fake_client2)):
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Test content.",
                "goal": "Test",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    job_id = resp.json()["id"]

    # Should start as PENDING
    job_resp = await client.get(f"/api/jobs/{job_id}", headers=auth_headers)
    assert job_resp.json()["status"] == "PENDING"

    # Simulate status transitions
    job = await db_session.get(SimulationJob, job_id)
    for status in [JobStatus.PROVISIONING, JobStatus.RUNNING, JobStatus.COMPLETED]:
        job.status = status
        await db_session.commit()
        await db_session.refresh(job)
        job_resp = await client.get(f"/api/jobs/{job_id}", headers=auth_headers)
        assert job_resp.json()["status"] == status.value
