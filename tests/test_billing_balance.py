"""
Stripe billing balance and history endpoint tests.

Covers:
- Balance for new user (zero)
- Balance after credits and multiple credits
- History with credit and debit entries
- Empty history for new user
- Auth guards on balance and history
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Balance tests
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
async def test_balance_requires_auth(client):
    """GET /billing/balance without auth returns 401."""
    response = await client.get("/api/billing/balance")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# History tests
# ---------------------------------------------------------------------------

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
async def test_history_requires_auth(client):
    """GET /billing/history without auth returns 401."""
    response = await client.get("/api/billing/history")
    assert response.status_code == 401
