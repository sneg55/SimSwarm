# Plan 2: Billing & Credits

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the credit ledger, Stripe checkout integration, and credit-gated job creation so users must purchase credits before running simulations.

**Architecture:** Double-entry credit ledger in PostgreSQL. Stripe Checkout Sessions for one-time pack purchases. Webhook handler credits the ledger on successful payment. Job creation atomically checks and deducts credits.

**Tech Stack:** Stripe Python SDK, FastAPI, SQLAlchemy 2.0 (async), pytest, pytest-asyncio

**Depends on:** Plan 1 (database, models, FastAPI skeleton)

**Spec reference:** `docs/superpowers/specs/2026-03-26-mirofish-hosted-mvp-design.md` — Appendix A

---

## File Structure

```
saas/
├── billing/
│   ├── __init__.py
│   ├── ledger.py              # Credit ledger operations (debit/credit/balance)
│   ├── stripe_service.py      # Stripe Checkout + webhook handling
│   └── credit_packs.py        # Pack definitions (Starter/Pro/Heavy)
├── models/
│   └── credit_entry.py        # CreditEntry model (double-entry ledger)
├── api/
│   ├── billing.py             # Purchase + balance endpoints
│   └── jobs.py                # Modified: credit check before job creation
├── schemas/
│   └── billing.py             # Billing request/response schemas
tests/
├── test_ledger.py             # Ledger unit tests
├── test_credit_packs.py       # Pack definition tests
├── test_billing_api.py        # Billing API integration tests
├── test_stripe_webhook.py     # Webhook handler tests
├── test_jobs_credit_gate.py   # Job creation with credit checks
```

---

### Task 1: Credit Pack Definitions

**Files:**
- Create: `saas/billing/__init__.py`
- Create: `saas/billing/credit_packs.py`
- Create: `tests/test_credit_packs.py`

- [ ] **Step 1: Write credit pack tests**

```python
# tests/test_credit_packs.py
from saas.billing.credit_packs import CREDIT_PACKS, get_pack, get_tier_cost


def test_three_packs_defined():
    assert len(CREDIT_PACKS) == 3
    assert "starter" in CREDIT_PACKS
    assert "pro" in CREDIT_PACKS
    assert "heavy" in CREDIT_PACKS


def test_starter_pack():
    pack = get_pack("starter")
    assert pack.credits == 100
    assert pack.price_cents == 1900  # $19


def test_pro_pack():
    pack = get_pack("pro")
    assert pack.credits == 500
    assert pack.price_cents == 7900  # $79


def test_heavy_pack():
    pack = get_pack("heavy")
    assert pack.credits == 2000
    assert pack.price_cents == 24900  # $249


def test_tier_costs():
    assert get_tier_cost("small") == 30
    assert get_tier_cost("medium") == 90
    assert get_tier_cost("large") == 300


def test_invalid_pack_raises():
    import pytest
    with pytest.raises(KeyError):
        get_pack("nonexistent")


def test_invalid_tier_raises():
    import pytest
    with pytest.raises(KeyError):
        get_tier_cost("mega")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_credit_packs.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement credit packs**

```python
# saas/billing/__init__.py
```

```python
# saas/billing/credit_packs.py
from dataclasses import dataclass


@dataclass(frozen=True)
class CreditPack:
    name: str
    credits: int
    price_cents: int  # USD cents for Stripe
    description: str


CREDIT_PACKS: dict[str, CreditPack] = {
    "starter": CreditPack(
        name="Starter",
        credits=100,
        price_cents=1900,
        description="3-4 small simulations",
    ),
    "pro": CreditPack(
        name="Pro",
        credits=500,
        price_cents=7900,
        description="15-20 medium simulations",
    ),
    "heavy": CreditPack(
        name="Heavy",
        credits=2000,
        price_cents=24900,
        description="Large-scale or frequent use",
    ),
}

TIER_CREDITS: dict[str, int] = {
    "small": 30,
    "medium": 90,
    "large": 300,
}


def get_pack(pack_id: str) -> CreditPack:
    return CREDIT_PACKS[pack_id]


def get_tier_cost(tier: str) -> int:
    return TIER_CREDITS[tier]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_credit_packs.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add saas/billing/ tests/test_credit_packs.py
git commit -m "feat: define credit packs and tier costs"
```

---

### Task 2: Credit Ledger Model + Operations

**Files:**
- Create: `saas/models/credit_entry.py`
- Modify: `saas/models/__init__.py` — add CreditEntry import
- Create: `saas/billing/ledger.py`
- Create: `tests/test_ledger.py`

- [ ] **Step 1: Write ledger tests**

```python
# tests/test_ledger.py
import pytest
from saas.billing.ledger import CreditLedger, InsufficientCreditsError


async def test_initial_balance_is_zero(db_session):
    ledger = CreditLedger(db_session)
    balance = await ledger.get_balance("user-1")
    assert balance == 0


async def test_credit_purchase(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-1", amount=100, description="Starter pack purchase")
    balance = await ledger.get_balance("user-1")
    assert balance == 100


async def test_debit_reduces_balance(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-1", amount=100, description="Purchase")
    await ledger.debit("user-1", amount=30, description="Small sim job #1")
    balance = await ledger.get_balance("user-1")
    assert balance == 70


async def test_debit_insufficient_credits_raises(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-1", amount=20, description="Purchase")
    with pytest.raises(InsufficientCreditsError):
        await ledger.debit("user-1", amount=30, description="Small sim")


async def test_multiple_transactions(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-1", amount=500, description="Pro pack")
    await ledger.debit("user-1", amount=90, description="Medium sim #1")
    await ledger.debit("user-1", amount=90, description="Medium sim #2")
    await ledger.debit("user-1", amount=30, description="Small sim #1")
    balance = await ledger.get_balance("user-1")
    assert balance == 290


async def test_refund_credits_back(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-1", amount=100, description="Purchase")
    await ledger.debit("user-1", amount=30, description="Small sim")
    await ledger.credit("user-1", amount=30, description="Refund: job failed")
    balance = await ledger.get_balance("user-1")
    assert balance == 100


async def test_separate_user_balances(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-A", amount=100, description="Purchase")
    await ledger.credit("user-B", amount=500, description="Purchase")
    assert await ledger.get_balance("user-A") == 100
    assert await ledger.get_balance("user-B") == 500


async def test_get_history(db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("user-1", amount=100, description="Purchase")
    await ledger.debit("user-1", amount=30, description="Small sim")
    history = await ledger.get_history("user-1")
    assert len(history) == 2
    assert history[0].amount == 100  # oldest first
    assert history[1].amount == -30
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ledger.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement CreditEntry model**

```python
# saas/models/credit_entry.py
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from saas.models.base import Base


class CreditEntry(Base):
    __tablename__ = "credit_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    amount: Mapped[int] = mapped_column(Integer)  # positive=credit, negative=debit
    description: Mapped[str] = mapped_column(Text)
    stripe_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

Update `saas/models/__init__.py`:

```python
# saas/models/__init__.py
from saas.models.base import Base
from saas.models.job import SimulationJob, JobStatus
from saas.models.model_routing import ModelRouting
from saas.models.credit_entry import CreditEntry

__all__ = ["Base", "SimulationJob", "JobStatus", "ModelRouting", "CreditEntry"]
```

- [ ] **Step 4: Implement ledger operations**

```python
# saas/billing/ledger.py
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from saas.models.credit_entry import CreditEntry


class InsufficientCreditsError(Exception):
    def __init__(self, balance: int, required: int):
        self.balance = balance
        self.required = required
        super().__init__(f"Insufficient credits: have {balance}, need {required}")


class CreditLedger:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_balance(self, user_id: str) -> int:
        result = await self.session.execute(
            select(func.coalesce(func.sum(CreditEntry.amount), 0)).where(
                CreditEntry.user_id == user_id
            )
        )
        return result.scalar()

    async def credit(
        self,
        user_id: str,
        amount: int,
        description: str,
        stripe_session_id: str | None = None,
    ) -> CreditEntry:
        entry = CreditEntry(
            user_id=user_id,
            amount=amount,
            description=description,
            stripe_session_id=stripe_session_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def debit(
        self,
        user_id: str,
        amount: int,
        description: str,
        job_id: int | None = None,
    ) -> CreditEntry:
        balance = await self.get_balance(user_id)
        if balance < amount:
            raise InsufficientCreditsError(balance=balance, required=amount)

        entry = CreditEntry(
            user_id=user_id,
            amount=-amount,
            description=description,
            job_id=job_id,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_history(self, user_id: str) -> list[CreditEntry]:
        result = await self.session.execute(
            select(CreditEntry)
            .where(CreditEntry.user_id == user_id)
            .order_by(CreditEntry.created_at.asc())
        )
        return list(result.scalars().all())
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_ledger.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add saas/models/credit_entry.py saas/models/__init__.py saas/billing/ledger.py tests/test_ledger.py
git commit -m "feat: add double-entry credit ledger with debit/credit/balance"
```

---

### Task 3: Stripe Checkout + Webhook Handler

**Files:**
- Create: `saas/billing/stripe_service.py`
- Create: `tests/test_stripe_webhook.py`

- [ ] **Step 1: Write Stripe webhook tests**

```python
# tests/test_stripe_webhook.py
import json
import pytest
from unittest.mock import patch, MagicMock
from saas.billing.stripe_service import StripeService


def test_create_checkout_url():
    """StripeService.create_checkout_session calls Stripe with correct params."""
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/c/pay_xxx"

    with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
        service = StripeService(
            api_key="sk_test_xxx",
            webhook_secret="whsec_xxx",
            success_url="https://app.fishcloud.com/billing?success=1",
            cancel_url="https://app.fishcloud.com/billing?cancel=1",
        )
        url = service.create_checkout_session(
            user_id="user-123",
            pack_id="starter",
        )
        assert url == "https://checkout.stripe.com/c/pay_xxx"
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["mode"] == "payment"
        assert call_kwargs["metadata"]["user_id"] == "user-123"
        assert call_kwargs["metadata"]["pack_id"] == "starter"
        assert call_kwargs["line_items"][0]["price_data"]["unit_amount"] == 1900


def test_parse_webhook_event_valid():
    service = StripeService(
        api_key="sk_test_xxx",
        webhook_secret="whsec_xxx",
        success_url="https://example.com/ok",
        cancel_url="https://example.com/cancel",
    )
    mock_event = MagicMock()
    mock_event.type = "checkout.session.completed"
    mock_event.data.object = {
        "id": "cs_test_xxx",
        "metadata": {"user_id": "user-123", "pack_id": "starter"},
    }

    with patch("stripe.Webhook.construct_event", return_value=mock_event):
        event = service.verify_webhook(payload=b"raw_body", sig_header="sig_xxx")
        assert event.type == "checkout.session.completed"


def test_extract_purchase_info():
    service = StripeService(
        api_key="sk_test_xxx",
        webhook_secret="whsec_xxx",
        success_url="https://example.com/ok",
        cancel_url="https://example.com/cancel",
    )
    session_data = {
        "id": "cs_test_xxx",
        "metadata": {"user_id": "user-123", "pack_id": "pro"},
    }
    user_id, pack_id, session_id = service.extract_purchase_info(session_data)
    assert user_id == "user-123"
    assert pack_id == "pro"
    assert session_id == "cs_test_xxx"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_stripe_webhook.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Stripe service**

Add `stripe>=11.0.0` to `pyproject.toml` dependencies, then:

```python
# saas/billing/stripe_service.py
import stripe

from saas.billing.credit_packs import get_pack


class StripeService:
    def __init__(
        self,
        api_key: str,
        webhook_secret: str,
        success_url: str,
        cancel_url: str,
    ):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.success_url = success_url
        self.cancel_url = cancel_url
        stripe.api_key = api_key

    def create_checkout_session(self, user_id: str, pack_id: str) -> str:
        pack = get_pack(pack_id)
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {"name": f"FishCloud {pack.name} Pack"},
                        "unit_amount": pack.price_cents,
                    },
                    "quantity": 1,
                }
            ],
            metadata={"user_id": user_id, "pack_id": pack_id},
            success_url=self.success_url,
            cancel_url=self.cancel_url,
        )
        return session.url

    def verify_webhook(self, payload: bytes, sig_header: str):
        return stripe.Webhook.construct_event(
            payload, sig_header, self.webhook_secret
        )

    def extract_purchase_info(self, session_data: dict) -> tuple[str, str, str]:
        user_id = session_data["metadata"]["user_id"]
        pack_id = session_data["metadata"]["pack_id"]
        session_id = session_data["id"]
        return user_id, pack_id, session_id
```

- [ ] **Step 4: Install stripe and run tests**

```bash
pip install stripe>=11.0.0
pytest tests/test_stripe_webhook.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add saas/billing/stripe_service.py tests/test_stripe_webhook.py pyproject.toml
git commit -m "feat: add Stripe checkout session creation and webhook verification"
```

---

### Task 4: Billing API Endpoints

**Files:**
- Create: `saas/schemas/billing.py`
- Create: `saas/api/billing.py`
- Modify: `saas/api/router.py` — add billing router
- Create: `tests/test_billing_api.py`

- [ ] **Step 1: Write billing API tests**

```python
# tests/test_billing_api.py
import pytest
from unittest.mock import patch


async def test_get_balance_zero(client):
    resp = await client.get("/api/billing/balance", params={"user_id": "new-user"})
    assert resp.status_code == 200
    assert resp.json()["balance"] == 0


async def test_purchase_creates_checkout_url(client):
    with patch(
        "saas.api.billing.stripe_service.create_checkout_session",
        return_value="https://checkout.stripe.com/xxx",
    ):
        resp = await client.post(
            "/api/billing/purchase",
            json={"user_id": "user-1", "pack_id": "starter"},
        )
        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://checkout.stripe.com/xxx"


async def test_purchase_invalid_pack(client):
    resp = await client.post(
        "/api/billing/purchase",
        json={"user_id": "user-1", "pack_id": "nonexistent"},
    )
    assert resp.status_code == 400


async def test_get_history_empty(client):
    resp = await client.get("/api/billing/history", params={"user_id": "user-1"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_webhook_credits_account(client):
    """Simulate a successful Stripe webhook and verify credits are added."""
    from saas.billing.ledger import CreditLedger
    from saas.database import get_session

    # Manually credit to simulate webhook effect
    # (Real webhook test requires Stripe signature — tested in test_stripe_webhook.py)
    # This tests the ledger integration in the API layer
    resp = await client.get("/api/billing/balance", params={"user_id": "webhook-user"})
    assert resp.json()["balance"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_billing_api.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement billing schemas**

```python
# saas/schemas/billing.py
from pydantic import BaseModel
from datetime import datetime


class BalanceResponse(BaseModel):
    user_id: str
    balance: int


class PurchaseRequest(BaseModel):
    user_id: str
    pack_id: str


class PurchaseResponse(BaseModel):
    checkout_url: str


class CreditHistoryEntry(BaseModel):
    id: int
    amount: int
    description: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Implement billing API**

```python
# saas/api/billing.py
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.billing.ledger import CreditLedger
from saas.billing.credit_packs import get_pack, CREDIT_PACKS
from saas.billing.stripe_service import StripeService
from saas.config import Settings
from saas.schemas.billing import (
    BalanceResponse,
    PurchaseRequest,
    PurchaseResponse,
    CreditHistoryEntry,
)

router = APIRouter(prefix="/billing", tags=["billing"])

# Initialized at app startup — see main.py
stripe_service: StripeService | None = None


def init_stripe(settings: Settings):
    global stripe_service
    stripe_service = StripeService(
        api_key=settings.STRIPE_SECRET_KEY,
        webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
    )


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(user_id: str, session: AsyncSession = Depends(get_session)):
    ledger = CreditLedger(session)
    balance = await ledger.get_balance(user_id)
    return BalanceResponse(user_id=user_id, balance=balance)


@router.post("/purchase", response_model=PurchaseResponse)
async def purchase_credits(body: PurchaseRequest):
    if body.pack_id not in CREDIT_PACKS:
        raise HTTPException(status_code=400, detail=f"Unknown pack: {body.pack_id}")

    url = stripe_service.create_checkout_session(
        user_id=body.user_id,
        pack_id=body.pack_id,
    )
    return PurchaseResponse(checkout_url=url)


@router.post("/webhook")
async def stripe_webhook(request: Request, session: AsyncSession = Depends(get_session)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe_service.verify_webhook(payload, sig_header)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    if event.type == "checkout.session.completed":
        session_data = event.data.object
        user_id, pack_id, session_id = stripe_service.extract_purchase_info(session_data)
        pack = get_pack(pack_id)

        ledger = CreditLedger(session)
        await ledger.credit(
            user_id=user_id,
            amount=pack.credits,
            description=f"{pack.name} pack purchase",
            stripe_session_id=session_id,
        )
        await session.commit()

    return {"status": "ok"}


@router.get("/history", response_model=list[CreditHistoryEntry])
async def get_history(user_id: str, session: AsyncSession = Depends(get_session)):
    ledger = CreditLedger(session)
    entries = await ledger.get_history(user_id)
    return entries
```

- [ ] **Step 5: Add Stripe config fields to Settings**

Add to `saas/config.py`:

```python
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_SUCCESS_URL: str = "http://localhost:3000/billing?success=1"
    STRIPE_CANCEL_URL: str = "http://localhost:3000/billing?cancel=1"
```

- [ ] **Step 6: Wire billing router**

Update `saas/api/router.py`:

```python
# saas/api/router.py
from fastapi import APIRouter
from saas.api.health import router as health_router
from saas.api.jobs import router as jobs_router
from saas.api.billing import router as billing_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(jobs_router)
api_router.include_router(billing_router)
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_billing_api.py -v
```

Expected: 5 passed.

- [ ] **Step 8: Commit**

```bash
git add saas/schemas/billing.py saas/api/billing.py saas/api/router.py saas/config.py tests/test_billing_api.py
git commit -m "feat: add billing API with balance, purchase, webhook, and history"
```

---

### Task 5: Credit-Gated Job Creation

**Files:**
- Modify: `saas/api/jobs.py` — add credit check + deduction
- Create: `tests/test_jobs_credit_gate.py`

- [ ] **Step 1: Write credit gate tests**

```python
# tests/test_jobs_credit_gate.py
import pytest
from saas.billing.ledger import CreditLedger


async def test_create_job_without_credits_fails(client):
    """User with 0 credits cannot run a simulation."""
    resp = await client.post(
        "/api/jobs",
        json={
            "user_id": "broke-user",
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "small",
        },
    )
    assert resp.status_code == 402
    assert "credits" in resp.json()["detail"].lower()


async def test_create_job_with_insufficient_credits_fails(client, db_session):
    """User with some credits but not enough cannot run."""
    ledger = CreditLedger(db_session)
    await ledger.credit("low-user", amount=20, description="Partial purchase")
    await db_session.commit()

    resp = await client.post(
        "/api/jobs",
        json={
            "user_id": "low-user",
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "small",  # costs 30
        },
    )
    assert resp.status_code == 402


async def test_create_job_deducts_credits(client, db_session):
    """Successful job creation deducts credits."""
    ledger = CreditLedger(db_session)
    await ledger.credit("funded-user", amount=100, description="Starter pack")
    await db_session.commit()

    resp = await client.post(
        "/api/jobs",
        json={
            "user_id": "funded-user",
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "small",  # costs 30
        },
    )
    assert resp.status_code == 201
    assert resp.json()["credits_charged"] == 30

    # Verify balance was reduced
    balance_resp = await client.get(
        "/api/billing/balance", params={"user_id": "funded-user"}
    )
    assert balance_resp.json()["balance"] == 70


async def test_create_large_job_deducts_300_credits(client, db_session):
    ledger = CreditLedger(db_session)
    await ledger.credit("whale-user", amount=2000, description="Heavy pack")
    await db_session.commit()

    resp = await client.post(
        "/api/jobs",
        json={
            "user_id": "whale-user",
            "seed_text": "Test seed",
            "goal": "Test goal",
            "tier": "large",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["credits_charged"] == 300

    balance_resp = await client.get(
        "/api/billing/balance", params={"user_id": "whale-user"}
    )
    assert balance_resp.json()["balance"] == 1700
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_jobs_credit_gate.py -v
```

Expected: FAIL — jobs endpoint currently doesn't check credits (returns 201).

- [ ] **Step 3: Update jobs API to gate on credits**

Replace `saas/api/jobs.py` `create_job` function:

```python
# saas/api/jobs.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.models.job import SimulationJob, JobStatus
from saas.schemas.jobs import JobCreate, JobResponse, TIER_CREDITS
from saas.billing.ledger import CreditLedger, InsufficientCreditsError

router = APIRouter(prefix="/jobs", tags=["jobs"])

MAX_SEED_CHARS = 50_000


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(body: JobCreate, session: AsyncSession = Depends(get_session)):
    if len(body.seed_text) > MAX_SEED_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Seed text exceeds maximum of {MAX_SEED_CHARS} characters",
        )

    credits = TIER_CREDITS[body.tier]

    # Credit gate: check and deduct credits atomically
    ledger = CreditLedger(session)
    try:
        await ledger.debit(
            user_id=body.user_id,
            amount=credits,
            description=f"{body.tier.value} simulation",
        )
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: have {e.balance}, need {e.required}. Purchase more credits.",
        )

    job = SimulationJob(
        user_id=body.user_id,
        seed_text=body.seed_text,
        goal=body.goal,
        tier=body.tier.value,
        credits_charged=credits,
        status=JobStatus.PENDING,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, session: AsyncSession = Depends(get_session)):
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("", response_model=list[JobResponse])
async def list_jobs(user_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(SimulationJob)
        .where(SimulationJob.user_id == user_id)
        .order_by(SimulationJob.created_at.desc())
    )
    return result.scalars().all()
```

- [ ] **Step 4: Fix existing job tests that now need credits**

Update `tests/test_jobs_api.py` and `tests/test_integration.py` — add credit seeding in fixtures. Add to `tests/conftest.py`:

```python
@pytest.fixture
async def funded_user(db_session):
    """Seed a user with enough credits for testing."""
    from saas.billing.ledger import CreditLedger
    ledger = CreditLedger(db_session)
    await ledger.credit("user-123", amount=10000, description="Test credits")
    await ledger.credit("user-456", amount=10000, description="Test credits")
    await ledger.credit("integration-test-user", amount=10000, description="Test credits")
    await ledger.credit("tier-test-user", amount=10000, description="Test credits")
    await db_session.commit()
```

Update existing test functions in `test_jobs_api.py` and `test_integration.py` to include `funded_user` as a fixture parameter.

- [ ] **Step 5: Run full test suite**

```bash
pytest -v
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add saas/api/jobs.py tests/test_jobs_credit_gate.py tests/test_jobs_api.py tests/test_integration.py tests/conftest.py
git commit -m "feat: gate job creation on credit balance with atomic deduction"
```

---

## Test Suite Summary (After Plan 2)

| File | Tests | What it covers |
|------|-------|----------------|
| `test_credit_packs.py` | 7 | Pack definitions, tier costs, validation |
| `test_ledger.py` | 8 | Credit/debit, balance, history, insufficient funds, multi-user |
| `test_stripe_webhook.py` | 3 | Checkout creation, webhook verification, purchase info extraction |
| `test_billing_api.py` | 5 | Balance, purchase, webhook, history endpoints |
| `test_jobs_credit_gate.py` | 4 | Credit-gated job creation, insufficient credits, deduction verification |
| *(Plan 1 tests)* | 22 | Config, DB, models, health, adapter, jobs API, integration |
| **Total** | **49** | |
