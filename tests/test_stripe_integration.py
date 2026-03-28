"""
Comprehensive Stripe billing integration tests for FishCloud.

Covers:
- Purchase flow (all packs, invalid pack, auth guard)
- Webhook handling (valid, bad signature, non-checkout events)
- Balance & history endpoints (new user, after credit, ordering, auth guards)
- Full purchase → webhook → balance verification flow
"""

from __future__ import annotations

import time
import hashlib
import hmac
import pytest
from unittest.mock import MagicMock, patch

from saas.billing.credit_packs import CREDIT_PACKS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stripe_session_mock(
    session_id: str = "cs_test_abc123",
    checkout_url: str = "https://checkout.stripe.com/pay/cs_test_abc123",
) -> MagicMock:
    """Return a minimal mock of a Stripe checkout Session object."""
    mock = MagicMock()
    mock.id = session_id
    mock.url = checkout_url
    return mock


def _make_checkout_completed_event(
    user_id: str,
    credits: int,
    pack_id: str = "starter",
    session_id: str = "cs_test_abc123",
    payment_intent: str | None = None,
) -> MagicMock:
    """Return a mock of a checkout.session.completed Stripe Event."""
    event = MagicMock()
    event.type = "checkout.session.completed"
    event.data.object.id = session_id
    event.data.object.payment_intent = payment_intent
    event.data.object.metadata = {
        "user_id": user_id,
        "pack_id": pack_id,
        "credits": str(credits),
    }
    return event


def _build_stripe_signature(payload: bytes, secret: str) -> str:
    """
    Build a valid-looking Stripe webhook signature header.
    Format: t=<timestamp>,v1=<hmac_sha256>
    """
    timestamp = int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    sig = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"


# ---------------------------------------------------------------------------
# Purchase flow tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_purchase_starter_returns_checkout_url(client, auth_headers):
    """POST /billing/purchase with pack_id=starter returns a checkout_url."""
    mock_session = _make_stripe_session_mock("cs_test_starter", "https://checkout.stripe.com/pay/cs_test_starter")

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        response = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "starter"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "cs_test_starter"
    assert data["checkout_url"] == "https://checkout.stripe.com/pay/cs_test_starter"


@pytest.mark.asyncio
async def test_purchase_pro_returns_checkout_url(client, auth_headers):
    """POST /billing/purchase with pack_id=pro returns a checkout_url."""
    mock_session = _make_stripe_session_mock("cs_test_pro", "https://checkout.stripe.com/pay/cs_test_pro")

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        response = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "pro"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "cs_test_pro"
    assert "checkout_url" in data


@pytest.mark.asyncio
async def test_purchase_heavy_returns_checkout_url(client, auth_headers):
    """POST /billing/purchase with pack_id=heavy returns a checkout_url."""
    mock_session = _make_stripe_session_mock("cs_test_heavy", "https://checkout.stripe.com/pay/cs_test_heavy")

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        response = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "heavy"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "cs_test_heavy"
    assert "checkout_url" in data


@pytest.mark.asyncio
async def test_purchase_stripe_receives_correct_metadata(client, auth_headers):
    """Verify Stripe.create is called with correct metadata for the starter pack."""
    pack = CREDIT_PACKS["starter"]
    mock_session = _make_stripe_session_mock()
    user_id = auth_headers["_user_id"]

    with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
        await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "starter"},
        )

    mock_create.assert_called_once()
    kwargs = mock_create.call_args.kwargs
    metadata = kwargs["metadata"]
    assert metadata["user_id"] == user_id
    assert metadata["pack_id"] == "starter"
    assert metadata["credits"] == str(pack.credits)

    line_items = kwargs["line_items"]
    assert len(line_items) == 1
    assert line_items[0]["price_data"]["unit_amount"] == pack.price_cents
    assert kwargs["mode"] == "payment"


@pytest.mark.asyncio
async def test_purchase_invalid_pack_returns_400(client, auth_headers):
    """Unknown pack_id returns HTTP 400."""
    response = await client.post(
        "/api/billing/purchase",
        headers=auth_headers,
        json={"pack_id": "invalid_pack_xyz"},
    )
    assert response.status_code == 400
    assert "invalid_pack_xyz" in response.json()["detail"]


@pytest.mark.asyncio
async def test_purchase_requires_auth(client):
    """POST /billing/purchase without a JWT token returns 401."""
    response = await client.post(
        "/api/billing/purchase",
        json={"pack_id": "starter"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Webhook tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_webhook_completes_checkout_credits_account(client, auth_headers):
    """
    Simulate a checkout.session.completed webhook with a mocked valid signature.
    Verify that credits are added to the user's ledger.
    """
    user_id = auth_headers["_user_id"]
    pack = CREDIT_PACKS["starter"]
    event_mock = _make_checkout_completed_event(
        user_id=user_id,
        credits=pack.credits,
        pack_id="starter",
        session_id="cs_test_wh_001",
    )

    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
        response = await client.post(
            "/api/billing/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify balance was credited
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.status_code == 200
    assert balance_resp.json()["balance"] == pack.credits


@pytest.mark.asyncio
async def test_webhook_invalid_signature_returns_400(client):
    """A webhook with a bad signature should return HTTP 400."""
    import stripe as stripe_module

    with patch(
        "saas.billing.stripe_service.stripe.Webhook.construct_event",
        side_effect=stripe_module.SignatureVerificationError("bad sig", "sig_header"),
    ):
        response = await client.post(
            "/api/billing/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=badsignature"},
        )

    assert response.status_code == 400
    assert "signature" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_ignores_non_checkout_events(client, auth_headers):
    """
    Events other than checkout.session.completed should be accepted (200)
    but no credits should be added.
    """
    other_event = MagicMock()
    other_event.type = "payment_intent.succeeded"

    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=other_event):
        response = await client.post(
            "/api/billing/webhook",
            content=b'{"type": "payment_intent.succeeded"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Balance must remain zero — no credits added
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 0


@pytest.mark.asyncio
async def test_webhook_missing_user_id_does_not_crash(client):
    """Webhook with missing user_id metadata should still return 200 gracefully."""
    event_mock = MagicMock()
    event_mock.type = "checkout.session.completed"
    event_mock.data.object.id = "cs_test_no_user"
    event_mock.data.object.metadata = {}  # no user_id or credits

    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
        response = await client.post(
            "/api/billing/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_webhook_unknown_pack_does_not_credit_account(client, auth_headers):
    """A completed checkout with an unknown pack_id should not alter the balance."""
    user_id = auth_headers["_user_id"]
    event_mock = _make_checkout_completed_event(
        user_id=user_id,
        credits=100,
        pack_id="nonexistent_pack",
        session_id="cs_test_unknown_pack",
    )

    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
        await client.post(
            "/api/billing/webhook",
            content=b'{}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 0


# ---------------------------------------------------------------------------
# Balance & History tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_balance_returns_zero_for_new_user(client, auth_headers):
    """A freshly registered user starts with a balance of 0."""
    response = await client.get("/api/billing/balance", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["balance"] == 0
    assert data["user_id"] == auth_headers["_user_id"]


@pytest.mark.asyncio
async def test_balance_after_credit_reflects_change(client, auth_headers, db_session):
    """After manually crediting a user, the balance endpoint returns the updated amount."""
    from saas.billing.ledger import CreditLedger

    user_id = auth_headers["_user_id"]
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id, amount=250, description="Manual top-up test")
    await db_session.commit()

    response = await client.get("/api/billing/balance", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["balance"] == 250


@pytest.mark.asyncio
async def test_balance_reflects_multiple_credits(client, auth_headers, db_session):
    """Multiple credit operations accumulate correctly in the balance."""
    from saas.billing.ledger import CreditLedger

    user_id = auth_headers["_user_id"]
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id, amount=100, description="First credit")
    await ledger.credit(user_id, amount=200, description="Second credit")
    await db_session.commit()

    response = await client.get("/api/billing/balance", headers=auth_headers)
    assert response.json()["balance"] == 300


@pytest.mark.asyncio
async def test_history_shows_credit_entries(client, auth_headers, db_session):
    """History endpoint returns credit entries in chronological order."""
    from saas.billing.ledger import CreditLedger

    user_id = auth_headers["_user_id"]
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id, amount=100, description="First", stripe_session_id="cs_001")
    await ledger.credit(user_id, amount=500, description="Second", stripe_session_id="cs_002")
    await db_session.commit()

    response = await client.get("/api/billing/history", headers=auth_headers)
    assert response.status_code == 200
    entries = response.json()
    assert len(entries) == 2
    assert entries[0]["amount"] == 100
    assert entries[0]["description"] == "First"
    assert entries[0]["stripe_session_id"] == "cs_001"
    assert entries[1]["amount"] == 500
    assert entries[1]["description"] == "Second"


@pytest.mark.asyncio
async def test_history_empty_for_new_user(client, auth_headers):
    """A new user with no transactions has an empty history."""
    response = await client.get("/api/billing/history", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_history_includes_debit_entries(client, auth_headers, db_session):
    """History includes debit (negative) entries along with credits."""
    from saas.billing.ledger import CreditLedger

    user_id = auth_headers["_user_id"]
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id, amount=1000, description="Top-up")
    await ledger.debit(user_id, amount=30, description="Job charge", job_id=42)
    await db_session.commit()

    response = await client.get("/api/billing/history", headers=auth_headers)
    entries = response.json()
    assert len(entries) == 2
    amounts = [e["amount"] for e in entries]
    assert 1000 in amounts
    assert -30 in amounts


@pytest.mark.asyncio
async def test_balance_requires_auth(client):
    """GET /billing/balance without auth returns 401."""
    response = await client.get("/api/billing/balance")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_history_requires_auth(client):
    """GET /billing/history without auth returns 401."""
    response = await client.get("/api/billing/history")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Full end-to-end: purchase → webhook → balance
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_purchase_to_credit_flow(client, auth_headers):
    """
    Full flow:
    1. Create a checkout session (mocked Stripe API).
    2. Simulate the checkout.session.completed webhook.
    3. Assert balance increased by the correct pack amount.
    """
    user_id = auth_headers["_user_id"]
    pack_id = "pro"
    pack = CREDIT_PACKS[pack_id]
    session_id = "cs_test_full_flow_001"

    # Step 1 — initiate purchase
    mock_session = _make_stripe_session_mock(
        session_id=session_id,
        checkout_url=f"https://checkout.stripe.com/pay/{session_id}",
    )
    with patch("stripe.checkout.Session.create", return_value=mock_session):
        purchase_resp = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": pack_id},
        )
    assert purchase_resp.status_code == 200
    assert purchase_resp.json()["session_id"] == session_id

    # Step 2 — simulate Stripe webhook
    event_mock = _make_checkout_completed_event(
        user_id=user_id,
        credits=pack.credits,
        pack_id=pack_id,
        session_id=session_id,
    )
    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
        webhook_resp = await client.post(
            "/api/billing/webhook",
            content=b'{"type": "checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert webhook_resp.status_code == 200

    # Step 3 — verify balance
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.status_code == 200
    assert balance_resp.json()["balance"] == pack.credits  # 500 for pro

    # Step 4 — verify history has exactly one entry from the webhook
    history_resp = await client.get("/api/billing/history", headers=auth_headers)
    entries = history_resp.json()
    assert len(entries) == 1
    assert entries[0]["amount"] == pack.credits
    assert session_id in entries[0]["description"]
    assert entries[0]["stripe_session_id"] == session_id


@pytest.mark.asyncio
async def test_full_purchase_heavy_pack_flow(client, auth_headers):
    """Full flow for the heavy pack — verifies 2000 credits are applied."""
    user_id = auth_headers["_user_id"]
    pack = CREDIT_PACKS["heavy"]
    session_id = "cs_test_heavy_flow"

    mock_session = _make_stripe_session_mock(session_id=session_id)
    with patch("stripe.checkout.Session.create", return_value=mock_session):
        resp = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "heavy"},
        )
    assert resp.status_code == 200

    event_mock = _make_checkout_completed_event(
        user_id=user_id,
        credits=pack.credits,
        pack_id="heavy",
        session_id=session_id,
    )
    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
        await client.post(
            "/api/billing/webhook",
            content=b'{}',
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 2000


@pytest.mark.asyncio
async def test_multiple_purchases_accumulate_credits(client, auth_headers):
    """Two separate webhook events for the same user accumulate credits."""
    user_id = auth_headers["_user_id"]
    pack = CREDIT_PACKS["starter"]  # 100 credits

    for i in range(2):
        event_mock = _make_checkout_completed_event(
            user_id=user_id,
            credits=pack.credits,
            pack_id="starter",
            session_id=f"cs_test_multi_{i}",
        )
        with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event_mock):
            await client.post(
                "/api/billing/webhook",
                content=b'{}',
                headers={"stripe-signature": "t=1,v1=fake"},
            )

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == pack.credits * 2  # 200
