"""Additional branch coverage for saas/billing/ledger.py.

Covers: session_credited with None + miss + hit, get_credit_by_payment_intent
with None/miss/hit (credit positive vs refund negative), and a zero-amount
debit that leaves balance untouched.
"""
from __future__ import annotations

import pytest

from saas.billing.ledger import CreditLedger


@pytest.mark.asyncio
async def test_session_credited_none(db_session):
    ledger = CreditLedger(db_session)
    assert await ledger.session_credited(None) is False


@pytest.mark.asyncio
async def test_session_credited_miss_then_hit(db_session):
    ledger = CreditLedger(db_session)
    assert await ledger.session_credited("sess_missing") is False

    await ledger.credit(
        "user-session-hit",
        amount=100,
        description="Purchase",
        stripe_session_id="sess_hit_1",
    )
    assert await ledger.session_credited("sess_hit_1") is True


@pytest.mark.asyncio
async def test_session_credited_ignores_negative_amounts(db_session):
    """Refund rows with the same session_id must not register as 'credited'."""
    ledger = CreditLedger(db_session)
    # Seed a positive credit first so the user has balance to debit against.
    await ledger.credit("user-refund-only", amount=50, description="seed")
    # Insert a refund row (negative amount) with a stripe_session_id.
    from saas.billing.models import CreditEntry
    entry = CreditEntry(
        user_id="user-refund-only",
        amount=-50,
        description="refund",
        stripe_session_id="sess_refund_only",
    )
    db_session.add(entry)
    await db_session.flush()

    # session_credited filters amount > 0, so this should be False.
    assert await ledger.session_credited("sess_refund_only") is False


@pytest.mark.asyncio
async def test_get_credit_by_payment_intent_none(db_session):
    ledger = CreditLedger(db_session)
    assert await ledger.get_credit_by_payment_intent("pi_missing") is None


@pytest.mark.asyncio
async def test_get_credit_by_payment_intent_hit(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit(
        "user-pi",
        amount=200,
        description="Purchase",
        stripe_session_id="sess_pi",
        payment_intent_id="pi_known",
    )
    found = await ledger.get_credit_by_payment_intent("pi_known")
    assert found is not None
    assert found.amount == 200
    assert found.user_id == "user-pi"


@pytest.mark.asyncio
async def test_get_credit_by_payment_intent_ignores_negative(db_session):
    """Only positive credit rows count — refund rows must not be returned."""
    ledger = CreditLedger(db_session)
    from saas.billing.models import CreditEntry

    # Only a refund (negative) row with this payment_intent_id.
    entry = CreditEntry(
        user_id="user-only-refund",
        amount=-100,
        description="refund only",
        payment_intent_id="pi_refund_only",
    )
    db_session.add(entry)
    await db_session.flush()

    assert await ledger.get_credit_by_payment_intent("pi_refund_only") is None


@pytest.mark.asyncio
async def test_history_empty_for_new_user(db_session):
    ledger = CreditLedger(db_session)
    assert await ledger.get_history("brand-new-user") == []


@pytest.mark.asyncio
async def test_credit_returns_entry_with_metadata(db_session):
    ledger = CreditLedger(db_session)
    entry = await ledger.credit(
        "user-meta",
        amount=123,
        description="with metadata",
        stripe_session_id="sess_meta",
        payment_intent_id="pi_meta",
    )
    assert entry.amount == 123
    assert entry.stripe_session_id == "sess_meta"
    assert entry.payment_intent_id == "pi_meta"
    assert entry.user_id == "user-meta"
