"""Branch coverage for saas/billing/api.py.

Covers:
- /billing/packs listing from DB (includes active filter + sort)
- /billing/purchase fallback to hardcoded packs when DB empty
- /billing/history auth guard
- webhook branches: idempotent duplicate session, charge.refunded for known
  and unknown payment_intent, purchase fallback for missing DB packs
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from saas.billing.credit_packs import CREDIT_PACKS
from saas.billing.models import CreditPack as CreditPackModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _checkout_event(user_id: str, pack_id: str, session_id: str, payment_intent: str | None = None):
    ev = MagicMock()
    ev.type = "checkout.session.completed"
    ev.data.object.id = session_id
    ev.data.object.payment_intent = payment_intent
    ev.data.object.metadata = {"user_id": user_id, "pack_id": pack_id}
    return ev


def _refund_event(payment_intent: str):
    ev = MagicMock()
    ev.type = "charge.refunded"
    ev.data.object.payment_intent = payment_intent
    return ev


# ---------------------------------------------------------------------------
# /billing/packs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_packs_lists_active_db_packs(client, db_session):
    """GET /billing/packs returns active packs from the DB ordered by sort_order."""
    db_session.add_all(
        [
            CreditPackModel(
                slug="alpha", name="Alpha", credits=10, price_cents=100,
                description="Alpha pack", active=True, sort_order=2,
            ),
            CreditPackModel(
                slug="beta", name="Beta", credits=20, price_cents=200,
                description="Beta pack", active=True, sort_order=1,
            ),
            CreditPackModel(
                slug="gamma", name="Gamma-inactive", credits=30, price_cents=300,
                description="Inactive", active=False, sort_order=0,
            ),
        ]
    )
    await db_session.commit()

    resp = await client.get("/api/billing/packs")
    assert resp.status_code == 200
    slugs = [p["slug"] for p in resp.json()]
    # Only active packs; ordered by sort_order (beta=1 before alpha=2)
    assert slugs == ["beta", "alpha"]


@pytest.mark.asyncio
async def test_packs_empty_when_no_active_rows(client):
    """GET /billing/packs returns [] when table is empty."""
    resp = await client.get("/api/billing/packs")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# /billing/purchase — DB pack beats hardcoded fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_purchase_uses_db_pack_when_present(client, auth_headers, db_session):
    """When an active DB pack exists, its credits/price are sent to Stripe."""
    db_session.add(
        CreditPackModel(
            slug="starter", name="Starter-DB", credits=777, price_cents=9999,
            description="override", active=True, sort_order=1,
        )
    )
    await db_session.commit()

    mock_session = MagicMock()
    mock_session.id = "cs_db_override"
    mock_session.url = "https://checkout.stripe.com/pay/cs_db_override"

    with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
        resp = await client.post(
            "/api/billing/purchase",
            headers=auth_headers,
            json={"pack_id": "starter"},
        )
    assert resp.status_code == 200

    kwargs = mock_create.call_args.kwargs
    assert kwargs["line_items"][0]["price_data"]["unit_amount"] == 9999
    assert kwargs["metadata"]["credits"] == "777"


# ---------------------------------------------------------------------------
# /billing/history — auth guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_history_requires_auth(client):
    resp = await client.get("/api/billing/history")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Webhook idempotency — duplicate session ignored
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_duplicate_session_skipped(client, auth_headers):
    """A second webhook with the same session_id must not double-credit the user."""
    user_id = auth_headers["_user_id"]
    pack = CREDIT_PACKS["starter"]

    event = _checkout_event(user_id, "starter", "cs_dup_001")
    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event):
        await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=fake"},
        )
        # Same session_id — should be skipped
        await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == pack.credits


# ---------------------------------------------------------------------------
# Webhook refund paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_webhook_refund_debits_original_credit(client, auth_headers):
    """charge.refunded event for a known payment_intent debits the correct user."""
    user_id = auth_headers["_user_id"]
    pack = CREDIT_PACKS["starter"]
    payment_intent = "pi_refund_known_001"

    # Step 1 — credit the account via a completed checkout
    completed = _checkout_event(user_id, "starter", "cs_refund_known", payment_intent)
    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=completed):
        await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=fake"},
        )

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == pack.credits

    # Step 2 — emit a charge.refunded webhook for that payment_intent
    refund = _refund_event(payment_intent)
    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=refund):
        resp = await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert resp.status_code == 200

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 0


@pytest.mark.asyncio
async def test_webhook_refund_unknown_payment_intent_ignored(client, auth_headers):
    """charge.refunded for an unseen payment_intent is a no-op."""
    refund = _refund_event("pi_unknown_abc")
    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=refund):
        resp = await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert resp.status_code == 200

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 0


@pytest.mark.asyncio
async def test_webhook_missing_pack_id_in_metadata(client, auth_headers):
    """Webhook with user_id but no pack_id in metadata returns 200 without crediting."""
    event = MagicMock()
    event.type = "checkout.session.completed"
    event.data.object.id = "cs_no_pack_id"
    event.data.object.payment_intent = None
    event.data.object.metadata = {"user_id": auth_headers["_user_id"]}  # missing pack_id

    with patch("saas.billing.stripe_service.stripe.Webhook.construct_event", return_value=event):
        resp = await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=fake"},
        )
    assert resp.status_code == 200

    bal = await client.get("/api/billing/balance", headers=auth_headers)
    assert bal.json()["balance"] == 0
