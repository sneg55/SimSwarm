"""Stripe webhook hardening tests — idempotency, dedup, metadata validation."""

import pytest
from unittest.mock import patch, MagicMock

from saas.billing.ledger import CreditLedger


# ── Task 1: session_credited ledger check ──────────────────────────────


async def test_session_credited_returns_false_for_new_session(db_session):
    ledger = CreditLedger(db_session)
    assert await ledger.session_credited("cs_never_seen") is False


async def test_session_credited_returns_true_after_credit(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit(
        user_id="u1",
        amount=100,
        description="pack purchase",
        stripe_session_id="cs_abc123",
    )
    await db_session.flush()
    assert await ledger.session_credited("cs_abc123") is True


async def test_session_credited_ignores_null_session_ids(db_session):
    ledger = CreditLedger(db_session)
    # Credit with no stripe_session_id (e.g. admin grant)
    await ledger.credit(user_id="u1", amount=50, description="admin grant")
    await db_session.flush()
    # Querying None should return False — nulls are not idempotency keys
    assert await ledger.session_credited(None) is False
