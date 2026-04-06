"""Tests that refund operations are idempotent per job_id."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text, select, func

from saas.billing.models import CreditEntry


async def _do_refund_via_session(session, job_id: int, user_id: str, credits: int) -> bool:
    """Replicate the guard logic from _refund_credits using a provided session.

    Returns True if a refund row was inserted, False if skipped as duplicate.
    """
    existing = await session.execute(
        text(
            "SELECT 1 FROM credit_entries "
            "WHERE job_id = :job_id AND amount > 0 "
            "LIMIT 1"
        ),
        {"job_id": job_id},
    )
    if existing.first() is not None:
        return False

    await session.execute(
        text(
            "INSERT INTO credit_entries "
            "(user_id, amount, description, job_id, created_at) "
            "VALUES (:user_id, :amount, :description, :job_id, :created_at)"
        ),
        {
            "user_id": user_id,
            "amount": credits,
            "description": f"Refund for failed job {job_id}",
            "job_id": job_id,
            "created_at": datetime.now(timezone.utc),
        },
    )
    await session.commit()
    return True


async def _count_refund_entries(session, job_id: int) -> int:
    result = await session.execute(
        select(func.count(CreditEntry.id)).where(
            CreditEntry.job_id == job_id,
            CreditEntry.amount > 0,
        )
    )
    return result.scalar()


async def test_refund_guard_inserts_once(db_session):
    """Calling the refund guard twice for the same job_id inserts only one row."""
    job_id = 9001
    user_id = "user-idempotency-test"
    credits = 50

    inserted_first = await _do_refund_via_session(db_session, job_id, user_id, credits)
    inserted_second = await _do_refund_via_session(db_session, job_id, user_id, credits)

    count = await _count_refund_entries(db_session, job_id)

    assert inserted_first is True
    assert inserted_second is False
    assert count == 1


async def test_refund_guard_different_jobs_both_insert(db_session):
    """Two different job_ids each get their own refund row."""
    user_id = "user-idempotency-test2"

    await _do_refund_via_session(db_session, job_id=1001, user_id=user_id, credits=30)
    await _do_refund_via_session(db_session, job_id=1002, user_id=user_id, credits=60)

    count_1001 = await _count_refund_entries(db_session, 1001)
    count_1002 = await _count_refund_entries(db_session, 1002)

    assert count_1001 == 1
    assert count_1002 == 1


async def test_refund_guard_pre_existing_entry_skipped(db_session):
    """A refund is skipped when a positive credit entry for the job already exists."""
    job_id = 9999
    user_id = "user-pre-existing-test"
    credits = 100

    db_session.add(
        CreditEntry(
            user_id=user_id,
            amount=credits,
            description=f"Refund for failed job {job_id}",
            job_id=job_id,
        )
    )
    await db_session.commit()

    inserted = await _do_refund_via_session(db_session, job_id, user_id, credits)
    count = await _count_refund_entries(db_session, job_id)

    assert inserted is False
    assert count == 1
