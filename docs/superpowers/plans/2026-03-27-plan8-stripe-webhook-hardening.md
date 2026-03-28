# Stripe Webhook Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Stripe webhook handling production-safe: idempotent, validated, and handling refund events.

**Architecture:** Add idempotency check via `stripe_session_id` uniqueness in `credit_entries`, validate credit amounts against pack definitions instead of trusting metadata, and add `charge.refunded` event handler.

**Tech Stack:** FastAPI, SQLAlchemy async, Stripe webhook events, pytest-asyncio

**GitHub Issue:** #1

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `saas/billing/ledger.py` | Modify | Add `session_credited()` idempotency check |
| `saas/api/billing.py` | Modify | Add idempotency, metadata validation, refund handler, logging |
| `tests/test_stripe_webhook_hardening.py` | Create | All new tests for this plan |

---

### Task 1: Idempotency — Ledger Check

**Files:**
- Modify: `saas/billing/ledger.py:12-38`
- Test: `tests/test_stripe_webhook_hardening.py`

- [ ] **Step 1: Write failing test for `session_credited()`**

```python
# tests/test_stripe_webhook_hardening.py
import pytest
from saas.billing.ledger import CreditLedger


async def test_session_credited_returns_false_for_new_session(db_session):
    ledger = CreditLedger(db_session)
    result = await ledger.session_credited("cs_new_session_123")
    assert result is False


async def test_session_credited_returns_true_after_credit(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit(
        user_id="user-1",
        amount=100,
        description="test",
        stripe_session_id="cs_existing_session",
    )
    await db_session.flush()
    result = await ledger.session_credited("cs_existing_session")
    assert result is True


async def test_session_credited_ignores_null_session_ids(db_session):
    ledger = CreditLedger(db_session)
    # Credit without stripe_session_id should not affect the check
    await ledger.credit(user_id="user-1", amount=50, description="manual")
    await db_session.flush()
    result = await ledger.session_credited("cs_anything")
    assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_stripe_webhook_hardening.py -v`
Expected: FAIL — `CreditLedger` has no `session_credited` method

- [ ] **Step 3: Implement `session_credited()` in ledger**

Add this method to `CreditLedger` class in `saas/billing/ledger.py` after `get_balance()`:

```python
async def session_credited(self, stripe_session_id: str) -> bool:
    """Return True if credits have already been added for this Stripe session."""
    result = await self.session.execute(
        select(func.count(CreditEntry.id)).where(
            CreditEntry.stripe_session_id == stripe_session_id,
            CreditEntry.amount > 0,
        )
    )
    return result.scalar() > 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_stripe_webhook_hardening.py::test_session_credited_returns_false_for_new_session tests/test_stripe_webhook_hardening.py::test_session_credited_returns_true_after_credit tests/test_stripe_webhook_hardening.py::test_session_credited_ignores_null_session_ids -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add saas/billing/ledger.py tests/test_stripe_webhook_hardening.py
git commit -m "feat: add session_credited() idempotency check to CreditLedger"
```

---

### Task 2: Idempotency — Webhook Dedup

**Files:**
- Modify: `saas/api/billing.py:62-92`
- Test: `tests/test_stripe_webhook_hardening.py`

- [ ] **Step 1: Write failing test for duplicate webhook**

Append to `tests/test_stripe_webhook_hardening.py`:

```python
from unittest.mock import patch, MagicMock


def _make_checkout_event(session_id: str, user_id: str, pack_id: str, credits: int):
    """Helper to build a mock Stripe checkout.session.completed event."""
    mock_event = MagicMock()
    mock_event.type = "checkout.session.completed"
    mock_event.data.object.id = session_id
    mock_event.data.object.metadata = {
        "user_id": user_id,
        "pack_id": pack_id,
        "credits": str(credits),
    }
    return mock_event


async def test_duplicate_webhook_does_not_double_credit(client, auth_headers):
    """Same checkout.session.completed delivered twice — credits added only once."""
    event = _make_checkout_event("cs_dup_test", auth_headers["_user_id"], "starter", 100)

    with patch("stripe.Webhook.construct_event", return_value=event):
        resp1 = await client.post(
            "/api/billing/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )
        resp2 = await client.post(
            "/api/billing/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )

    assert resp1.status_code == 200
    assert resp2.status_code == 200

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 100  # NOT 200


async def test_duplicate_webhook_returns_200(client, auth_headers):
    """Duplicate webhook should still return 200 (Stripe expects this)."""
    event = _make_checkout_event("cs_dup_200", auth_headers["_user_id"], "starter", 100)

    with patch("stripe.Webhook.construct_event", return_value=event):
        resp1 = await client.post(
            "/api/billing/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )
        resp2 = await client.post(
            "/api/billing/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )

    assert resp2.status_code == 200
    assert resp2.json()["status"] == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_stripe_webhook_hardening.py::test_duplicate_webhook_does_not_double_credit -v`
Expected: FAIL — balance is 200 (credits added twice)

- [ ] **Step 3: Add idempotency check to webhook handler**

Modify `stripe_webhook()` in `saas/api/billing.py`. Replace lines 76-91:

```python
    if event.type == "checkout.session.completed":
        stripe_session = event.data.object
        user_id = stripe_session.metadata.get("user_id")
        pack_id = stripe_session.metadata.get("pack_id", "")
        stripe_session_id = stripe_session.id

        if not user_id:
            return {"status": "ok"}

        ledger = CreditLedger(session)

        # Idempotency: skip if already credited for this session
        if await ledger.session_credited(stripe_session_id):
            logger.info("Webhook duplicate: session %s already credited", stripe_session_id)
            return {"status": "ok"}

        # Validate credits against pack definition (don't trust metadata)
        try:
            pack = get_pack(pack_id)
            credits = pack.credits
        except KeyError:
            logger.warning("Webhook: unknown pack_id '%s' in session %s", pack_id, stripe_session_id)
            return {"status": "ok"}

        await ledger.credit(
            user_id=user_id,
            amount=credits,
            description=f"Credit purchase ({pack_id}) via Stripe session {stripe_session_id}",
            stripe_session_id=stripe_session_id,
        )
        await session.commit()
        logger.info("Credited %d credits to user %s (session %s)", credits, user_id, stripe_session_id)
```

Also add at the top of `billing.py`:

```python
import logging

logger = logging.getLogger(__name__)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_stripe_webhook_hardening.py::test_duplicate_webhook_does_not_double_credit tests/test_stripe_webhook_hardening.py::test_duplicate_webhook_returns_200 -v`
Expected: 2 PASS

- [ ] **Step 5: Run all existing billing tests to check for regressions**

Run: `pytest tests/test_stripe_integration.py tests/test_billing_api.py tests/test_stripe_webhook.py -v`
Expected: All pass. Note: `test_full_purchase_to_credit_flow` may need updating if it uses raw `credits` from metadata — check and fix if needed.

- [ ] **Step 6: Commit**

```bash
git add saas/api/billing.py tests/test_stripe_webhook_hardening.py
git commit -m "feat: add webhook idempotency — deduplicate on stripe_session_id"
```

---

### Task 3: Metadata Validation

**Files:**
- Modify: `saas/api/billing.py` (already modified in Task 2)
- Test: `tests/test_stripe_webhook_hardening.py`

- [ ] **Step 1: Write failing tests for metadata validation**

Append to `tests/test_stripe_webhook_hardening.py`:

```python
async def test_webhook_credits_match_pack_definition(client, auth_headers):
    """Credits come from pack definition, not from metadata."""
    # Metadata says 9999 credits, but pack is "starter" which is 100
    event = _make_checkout_event("cs_pack_val", auth_headers["_user_id"], "starter", 9999)

    with patch("stripe.Webhook.construct_event", return_value=event):
        await client.post(
            "/api/billing/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )

    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 100  # pack definition, not 9999


async def test_webhook_with_unknown_pack_id_does_not_credit(client, auth_headers):
    """Unknown pack_id in metadata — no credits added."""
    event = _make_checkout_event("cs_bad_pack", auth_headers["_user_id"], "nonexistent", 500)

    with patch("stripe.Webhook.construct_event", return_value=event):
        resp = await client.post(
            "/api/billing/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )

    assert resp.status_code == 200
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 0


async def test_webhook_with_missing_pack_id_does_not_credit(client, auth_headers):
    """No pack_id in metadata — no credits added."""
    mock_event = MagicMock()
    mock_event.type = "checkout.session.completed"
    mock_event.data.object.id = "cs_no_pack"
    mock_event.data.object.metadata = {
        "user_id": auth_headers["_user_id"],
        "credits": "100",
        # no pack_id
    }

    with patch("stripe.Webhook.construct_event", return_value=mock_event):
        resp = await client.post(
            "/api/billing/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )

    assert resp.status_code == 200
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 0
```

- [ ] **Step 2: Run tests to verify they pass (implementation already done in Task 2)**

Run: `pytest tests/test_stripe_webhook_hardening.py::test_webhook_credits_match_pack_definition tests/test_stripe_webhook_hardening.py::test_webhook_with_unknown_pack_id_does_not_credit tests/test_stripe_webhook_hardening.py::test_webhook_with_missing_pack_id_does_not_credit -v`
Expected: 3 PASS (the Task 2 implementation already validates via pack lookup)

- [ ] **Step 3: Commit**

```bash
git add tests/test_stripe_webhook_hardening.py
git commit -m "test: add metadata validation tests for Stripe webhook"
```

---

### Task 4: Refund Webhook Handler

**Files:**
- Modify: `saas/api/billing.py`
- Modify: `saas/billing/ledger.py`
- Test: `tests/test_stripe_webhook_hardening.py`

- [ ] **Step 1: Write failing tests for refund handling**

Append to `tests/test_stripe_webhook_hardening.py`:

```python
def _make_refund_event(charge_id: str, payment_intent_id: str, amount_refunded: int):
    """Helper to build a mock Stripe charge.refunded event."""
    mock_event = MagicMock()
    mock_event.type = "charge.refunded"
    mock_event.data.object.id = charge_id
    mock_event.data.object.payment_intent = payment_intent_id
    mock_event.data.object.amount_refunded = amount_refunded  # in cents
    mock_event.data.object.metadata = {}  # charge metadata is separate from session
    return mock_event


async def test_refund_webhook_debits_credits(client, auth_headers):
    """charge.refunded should debit credits for the matching session."""
    user_id = auth_headers["_user_id"]

    # First, credit the user via a checkout webhook
    checkout_event = _make_checkout_event("cs_refund_test", user_id, "starter", 100)
    # Add payment_intent to the checkout session metadata
    checkout_event.data.object.payment_intent = "pi_refund_test"

    with patch("stripe.Webhook.construct_event", return_value=checkout_event):
        await client.post(
            "/api/billing/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )

    # Verify credits were added
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 100

    # Now simulate a full refund
    refund_event = _make_refund_event("ch_123", "pi_refund_test", 1900)

    with patch("stripe.Webhook.construct_event", return_value=refund_event):
        resp = await client.post(
            "/api/billing/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )

    assert resp.status_code == 200
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 0


async def test_refund_for_unknown_session_returns_200(client):
    """Refund for untracked payment — return 200, no crash."""
    refund_event = _make_refund_event("ch_unknown", "pi_unknown", 1900)

    with patch("stripe.Webhook.construct_event", return_value=refund_event):
        resp = await client.post(
            "/api/billing/webhook",
            content=b"payload",
            headers={"stripe-signature": "valid"},
        )

    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_stripe_webhook_hardening.py::test_refund_webhook_debits_credits -v`
Expected: FAIL — no refund handler exists

- [ ] **Step 3: Add `get_credit_by_payment_intent()` to ledger**

Add to `CreditLedger` in `saas/billing/ledger.py`:

```python
async def get_credit_by_payment_intent(self, payment_intent_id: str) -> CreditEntry | None:
    """Find the credit entry linked to a Stripe payment intent."""
    # Stripe session IDs contain the payment intent reference, but we store
    # session_id. We need to look up by the payment_intent stored during checkout.
    # For now, we store payment_intent_id in the description or a dedicated column.
    # Fallback: search for entries where stripe_session_id is set and description
    # mentions the payment intent.
    result = await self.session.execute(
        select(CreditEntry).where(
            CreditEntry.payment_intent_id == payment_intent_id,
            CreditEntry.amount > 0,
        )
    )
    return result.scalar_one_or_none()
```

Add `payment_intent_id` column to `CreditEntry` in `saas/models/credit_entry.py`:

```python
payment_intent_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
```

- [ ] **Step 4: Store `payment_intent` on credit entry during checkout webhook**

Update the checkout handler in `saas/api/billing.py` to extract and store payment_intent:

```python
    if event.type == "checkout.session.completed":
        stripe_session = event.data.object
        user_id = stripe_session.metadata.get("user_id")
        pack_id = stripe_session.metadata.get("pack_id", "")
        stripe_session_id = stripe_session.id
        payment_intent_id = getattr(stripe_session, "payment_intent", None)

        if not user_id:
            return {"status": "ok"}

        ledger = CreditLedger(session)

        if await ledger.session_credited(stripe_session_id):
            logger.info("Webhook duplicate: session %s already credited", stripe_session_id)
            return {"status": "ok"}

        try:
            pack = get_pack(pack_id)
            credits = pack.credits
        except KeyError:
            logger.warning("Webhook: unknown pack_id '%s' in session %s", pack_id, stripe_session_id)
            return {"status": "ok"}

        await ledger.credit(
            user_id=user_id,
            amount=credits,
            description=f"Credit purchase ({pack_id}) via Stripe session {stripe_session_id}",
            stripe_session_id=stripe_session_id,
            payment_intent_id=payment_intent_id,
        )
        await session.commit()
        logger.info("Credited %d credits to user %s (session %s)", credits, user_id, stripe_session_id)
```

Update `CreditLedger.credit()` signature to accept `payment_intent_id`:

```python
async def credit(
    self,
    user_id: str,
    amount: int,
    description: str,
    stripe_session_id: str | None = None,
    payment_intent_id: str | None = None,
) -> CreditEntry:
    entry = CreditEntry(
        user_id=user_id,
        amount=amount,
        description=description,
        stripe_session_id=stripe_session_id,
        payment_intent_id=payment_intent_id,
    )
    self.session.add(entry)
    await self.session.flush()
    return entry
```

- [ ] **Step 5: Add refund event handler to webhook**

Add to `stripe_webhook()` in `saas/api/billing.py`, after the checkout handler:

```python
    elif event.type == "charge.refunded":
        charge = event.data.object
        payment_intent_id = getattr(charge, "payment_intent", None)

        if not payment_intent_id:
            logger.warning("Refund webhook missing payment_intent")
            return {"status": "ok"}

        ledger = CreditLedger(session)
        original_credit = await ledger.get_credit_by_payment_intent(payment_intent_id)

        if not original_credit:
            logger.warning("Refund: no credit entry for payment_intent %s", payment_intent_id)
            return {"status": "ok"}

        # Debit the full credited amount back
        await ledger.debit(
            user_id=original_credit.user_id,
            amount=original_credit.amount,
            description=f"Refund for payment_intent {payment_intent_id}",
        )
        await session.commit()
        logger.info(
            "Refunded %d credits from user %s (payment_intent %s)",
            original_credit.amount, original_credit.user_id, payment_intent_id,
        )
```

- [ ] **Step 6: Update conftest.py to register new column**

In `tests/conftest.py`, ensure `CreditEntry` import triggers table creation with the new column. This should work automatically since `CreditEntry` is already imported.

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_stripe_webhook_hardening.py -v`
Expected: All pass

- [ ] **Step 8: Run full test suite to check regressions**

Run: `pytest tests/ -v --timeout=30`
Expected: All pass. If `test_stripe_integration.py` tests fail because `ledger.credit()` now has a new param, they should still work since `payment_intent_id` defaults to `None`.

- [ ] **Step 9: Create Alembic migration for `payment_intent_id` column**

Run: `alembic revision --autogenerate -m "add payment_intent_id to credit_entries"`

Verify the generated migration adds the column and index. Edit if needed.

- [ ] **Step 10: Commit**

```bash
git add saas/billing/ledger.py saas/api/billing.py saas/models/credit_entry.py tests/test_stripe_webhook_hardening.py alembic/versions/
git commit -m "feat: add refund webhook handler with payment_intent tracking"
```

---

### Task 5: Existing Test Fixup

**Files:**
- Modify: `tests/test_stripe_integration.py` (if any tests broke)

- [ ] **Step 1: Run all Stripe/billing tests**

Run: `pytest tests/test_stripe_integration.py tests/test_billing_api.py tests/test_stripe_webhook.py tests/test_ledger.py tests/test_credit_packs.py tests/test_jobs_credit_gate.py tests/test_stripe_webhook_hardening.py -v`

- [ ] **Step 2: Fix any failures**

The most likely breakage is in `test_stripe_integration.py` where existing tests use raw `credits` from metadata. The webhook now ignores the `credits` metadata field and looks up the pack instead. Tests that forge webhook events with a valid `pack_id` in metadata will still pass. Tests that forge events with no `pack_id` or invalid `pack_id` will now get 0 credits — update those tests to include a valid `pack_id`.

For `test_full_purchase_to_credit_flow` and similar: ensure the mocked Stripe event includes `pack_id` in metadata (it should already since `create_checkout_session` puts it there).

- [ ] **Step 3: Commit any fixups**

```bash
git add tests/
git commit -m "fix: update existing Stripe tests for pack-validated webhook handler"
```
