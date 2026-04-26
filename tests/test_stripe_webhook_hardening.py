"""Stripe webhook hardening tests — idempotency, dedup, metadata validation."""

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


def _make_checkout_event(session_id: str, user_id: str, pack_id: str = "starter", credits: str = "100", payment_intent: str | None = None):
    """Build a mock Stripe checkout.session.completed event."""
    metadata = {"user_id": user_id, "pack_id": pack_id, "credits": credits}
    session_obj = MagicMock()
    session_obj.id = session_id
    session_obj.metadata = metadata
    session_obj.payment_intent = payment_intent

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


# ── Helpers: refund events ─────────────────────────────────────────────


def _make_refund_event(charge_id, payment_intent_id, amount_refunded):
    mock_event = MagicMock()
    mock_event.type = "charge.refunded"
    mock_event.data.object.id = charge_id
    mock_event.data.object.payment_intent = payment_intent_id
    mock_event.data.object.amount_refunded = amount_refunded
    mock_event.data.object.metadata = {}
    return mock_event


# ── Task 4: Refund webhook handler ────────────────────────────────────


async def test_refund_webhook_debits_credits(client, auth_headers, db_session):
    """Credit user via checkout (with payment_intent), then refund → balance 0."""
    user_id = auth_headers["_user_id"]

    # 1. Credit via checkout with a payment_intent
    checkout_event = _make_checkout_event(
        "cs_refund_test", user_id, payment_intent="pi_test"
    )
    resp = await _post_webhook(client, checkout_event)
    assert resp.status_code == 200

    # Verify credits were added
    ledger = CreditLedger(db_session)
    balance = await ledger.get_balance(user_id)
    assert balance == 100

    # 2. Send refund event with same payment_intent
    refund_event = _make_refund_event("ch_test", "pi_test", 1000)
    resp = await _post_webhook(client, refund_event)
    assert resp.status_code == 200

    # 3. Balance should be 0
    balance = await ledger.get_balance(user_id)
    assert balance == 0


async def test_refund_for_unknown_session_returns_200(client, auth_headers):
    """Refund for unknown payment_intent returns 200, no crash."""
    refund_event = _make_refund_event("ch_unknown", "pi_unknown", 5000)
    resp = await _post_webhook(client, refund_event)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ── Regression: Stripe SDK objects raise AttributeError when a key is absent ──


class _StripeObjectStub:
    """Mimics stripe._stripe_object.StripeObject: missing keys raise AttributeError
    on attribute access (rather than returning None like a normal MagicMock)."""

    def __init__(self, **fields):
        self._fields = fields

    def __getattr__(self, name):
        if name in self._fields:
            return self._fields[name]
        raise AttributeError(name)


async def test_checkout_webhook_with_no_metadata_field_returns_200(client):
    """Stripe dashboard "Send test webhook" can deliver a session object
    without a metadata key. Accessing `.metadata` then raised AttributeError
    and returned 500 — Stripe would then retry forever. Should 200 + log."""
    session_obj = _StripeObjectStub(id="cs_no_metadata")
    event = MagicMock()
    event.type = "checkout.session.completed"
    event.data.object = session_obj

    resp = await _post_webhook(client, event)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_refund_webhook_with_no_payment_intent_returns_200(client):
    """charge.refunded without a payment_intent key should not crash."""
    charge_obj = _StripeObjectStub(id="ch_no_pi")
    event = MagicMock()
    event.type = "charge.refunded"
    event.data.object = charge_obj

    resp = await _post_webhook(client, event)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
