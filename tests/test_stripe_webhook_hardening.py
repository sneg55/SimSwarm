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


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_checkout_event(session_id: str, user_id: str, pack_id: str = "starter", credits: str = "100"):
    """Build a mock Stripe checkout.session.completed event."""
    metadata = {"user_id": user_id, "pack_id": pack_id, "credits": credits}
    session_obj = MagicMock()
    session_obj.id = session_id
    session_obj.metadata = metadata

    event = MagicMock()
    event.type = "checkout.session.completed"
    event.data.object = session_obj
    return event


def _make_checkout_event_no_pack(session_id: str, user_id: str, credits: str = "100"):
    """Build a mock event with no pack_id in metadata."""
    metadata = {"user_id": user_id, "credits": credits}
    session_obj = MagicMock()
    session_obj.id = session_id
    session_obj.metadata = metadata

    event = MagicMock()
    event.type = "checkout.session.completed"
    event.data.object = session_obj
    return event


async def _post_webhook(client, event):
    """Post a fake webhook request, patching Stripe signature verification."""
    with patch("stripe.Webhook.construct_event", return_value=event):
        return await client.post(
            "/api/billing/webhook",
            content=b'{}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )


# ── Task 2: Webhook idempotency dedup ──────────────────────────────────


async def test_duplicate_webhook_does_not_double_credit(client, auth_headers, db_session):
    user_id = auth_headers["_user_id"]
    event = _make_checkout_event("cs_dup_test", user_id)

    resp1 = await _post_webhook(client, event)
    assert resp1.status_code == 200

    resp2 = await _post_webhook(client, event)
    assert resp2.status_code == 200

    # Balance should be pack credits (100), NOT 200
    ledger = CreditLedger(db_session)
    balance = await ledger.get_balance(user_id)
    assert balance == 100


async def test_duplicate_webhook_returns_200(client, auth_headers):
    user_id = auth_headers["_user_id"]
    event = _make_checkout_event("cs_dup_200", user_id)

    await _post_webhook(client, event)
    resp = await _post_webhook(client, event)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── Task 3: Metadata validation ────────────────────────────────────────


async def test_webhook_credits_match_pack_definition(client, auth_headers, db_session):
    """Metadata says 9999 credits but pack is 'starter' (100) → balance is 100."""
    user_id = auth_headers["_user_id"]
    event = _make_checkout_event("cs_tamper", user_id, pack_id="starter", credits="9999")

    await _post_webhook(client, event)

    ledger = CreditLedger(db_session)
    balance = await ledger.get_balance(user_id)
    assert balance == 100


async def test_webhook_with_unknown_pack_id_does_not_credit(client, auth_headers, db_session):
    user_id = auth_headers["_user_id"]
    event = _make_checkout_event("cs_unknown", user_id, pack_id="nonexistent", credits="500")

    resp = await _post_webhook(client, event)
    assert resp.status_code == 200

    ledger = CreditLedger(db_session)
    balance = await ledger.get_balance(user_id)
    assert balance == 0


async def test_webhook_with_missing_pack_id_does_not_credit(client, auth_headers, db_session):
    user_id = auth_headers["_user_id"]
    event = _make_checkout_event_no_pack("cs_nopack", user_id, credits="500")

    resp = await _post_webhook(client, event)
    assert resp.status_code == 200

    ledger = CreditLedger(db_session)
    balance = await ledger.get_balance(user_id)
    assert balance == 0
