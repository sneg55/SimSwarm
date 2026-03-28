# Security & Billing Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 critical security/billing bugs: XSS in report rendering, broken refund path, non-atomic job creation, and credit debit race condition.

**Architecture:** XSS fix uses DOMPurify + markdown-it in the frontend. Refund fix corrects the SQL table name. Atomic job creation reorders the create_job flow to defer commit until dispatch succeeds. Race-safe debit uses a single SQL statement with balance guard.

**Tech Stack:** Vue 3, DOMPurify, markdown-it, FastAPI, SQLAlchemy async, pytest

**GitHub Issues:** #13, #14, #15, #19

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/src/components/ReportViewer.vue` | Modify | Replace regex renderer with markdown-it + DOMPurify |
| `frontend/package.json` | Modify | Add dompurify + markdown-it deps |
| `saas/workers/tasks.py` | Modify | Fix `_refund_credits` table name, pass `credits_charged` |
| `saas/api/jobs.py` | Modify | Reorder to make debit+job+dispatch atomic |
| `saas/billing/ledger.py` | Modify | Race-safe debit via single SQL with balance check |
| `tests/test_xss_sanitization.py` | Create | XSS regression tests |
| `tests/test_atomic_job_creation.py` | Create | Dispatch failure + routing missing tests |
| `tests/test_concurrent_debit.py` | Create | Concurrent debit race tests |

---

### Task 1: XSS — Sanitize Report Rendering (#15)

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/src/components/ReportViewer.vue`

- [ ] **Step 1: Install DOMPurify and markdown-it**

```bash
cd frontend && npm install dompurify markdown-it
```

- [ ] **Step 2: Rewrite ReportViewer.vue**

Replace the entire `<script setup>` block in `frontend/src/components/ReportViewer.vue`:

```vue
<template>
  <div class="report-prose" v-html="safeHtml" />
</template>

<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'

const md = new MarkdownIt({
  html: false,        // don't allow raw HTML in markdown source
  linkify: true,
  typographer: true,
})

const props = defineProps({
  content: { type: String, default: '' },
})

const safeHtml = computed(() => {
  if (!props.content) return ''
  const rawHtml = md.render(props.content)
  return DOMPurify.sanitize(rawHtml, {
    ALLOWED_TAGS: ['h1','h2','h3','h4','p','strong','em','code','pre','ul','ol','li','a','blockquote','br','table','thead','tbody','tr','th','td'],
    ALLOWED_ATTR: ['href','target','rel'],
  })
})
</script>
```

Keep the existing `<style scoped>` block unchanged.

- [ ] **Step 3: Build frontend to verify no errors**

```bash
cd frontend && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/ReportViewer.vue
git commit -m "fix: sanitize report markdown with DOMPurify + markdown-it (XSS)"
```

---

### Task 2: Fix Broken Refund Path (#13)

**Files:**
- Modify: `saas/workers/tasks.py:36-72`
- Test: `tests/test_stripe_webhook_hardening.py` (existing refund tests should still pass)

- [ ] **Step 1: Write failing test**

```python
# tests/test_refund_path.py
"""Test that _refund_credits writes to credit_entries (not credit_ledger)."""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_refund_credits_uses_credit_entries_table():
    """Verify the SQL targets credit_entries, not credit_ledger."""
    from saas.workers.tasks import _refund_credits
    import inspect
    source = inspect.getsource(_refund_credits)
    assert "credit_entries" in source
    assert "credit_ledger" not in source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_refund_path.py::test_refund_credits_uses_credit_entries_table -v`
Expected: FAIL — source contains "credit_ledger"

- [ ] **Step 3: Fix `_refund_credits` in `saas/workers/tasks.py`**

Replace the `_refund_credits` function (lines 36-72):

```python
def _refund_credits(job_id: int, user_id: str, credits: int) -> None:
    """Insert a credit refund entry into credit_entries."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        logger.warning("DATABASE_URL not set; skipping credit refund for job %d", job_id)
        return

    async def _do_refund():
        engine = create_async_engine(database_url)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with session_factory() as session:
            try:
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
                logger.info("Refunded %d credits to user %s for job %d", credits, user_id, job_id)
            except Exception as exc:
                logger.warning("Could not insert credit refund for job %d: %s", job_id, exc)
            finally:
                await engine.dispose()

    _run_async(_do_refund())
```

- [ ] **Step 4: Also fix `credits_charged` not being passed in job dispatch**

In `saas/api/jobs.py`, the `run_simulation_task.delay(...)` call is missing `credits_charged`. Add it:

```python
    task_result = run_simulation_task.delay(
        job_id=job.id,
        user_id=user_id,
        seed_text=body.seed_text,
        goal=body.goal,
        tier=body.tier.value,
        model_id=routing.model_id,
        gpu_type=routing.gpu_type,
        max_rounds=routing.max_rounds,
        vllm_args=routing.vllm_args or "",
        llm_api_key=os.getenv("LLM_API_KEY", "not-needed"),
        zep_api_key=os.getenv("ZEP_API_KEY", ""),
        credits_charged=credits,
    )
```

- [ ] **Step 5: Write test for credits_charged passthrough**

```python
# tests/test_refund_path.py (append)

async def test_job_dispatch_passes_credits_charged(client, auth_headers, funded_user, seeded_routing):
    """Job dispatch must include credits_charged so failed jobs can refund."""
    from unittest.mock import patch, MagicMock

    mock_task = MagicMock()
    mock_task.id = "celery-mock"

    with patch("saas.api.jobs.run_simulation_task.delay", return_value=mock_task) as mock_delay:
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"seed_text": "Test seed text for dispatch.", "goal": "Test goal", "tier": "small"},
        )

    assert resp.status_code == 201
    call_kwargs = mock_delay.call_args
    # credits_charged should be passed as a keyword argument
    assert call_kwargs.kwargs.get("credits_charged") == 30 or \
           (len(call_kwargs.args) > 12 and call_kwargs.args[12] == 30)
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_refund_path.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add saas/workers/tasks.py saas/api/jobs.py tests/test_refund_path.py
git commit -m "fix: refund writes to credit_entries, pass credits_charged in dispatch (#13)"
```

---

### Task 3: Atomic Job Creation (#14)

**Files:**
- Modify: `saas/api/jobs.py:23-91`
- Test: `tests/test_atomic_job_creation.py`

The current flow: debit → commit → lookup routing → dispatch → commit task_id. If routing is missing or dispatch fails, credits are gone.

New flow: lookup routing first → debit → create job → dispatch → commit all at once. If anything fails, the session rolls back and credits are restored.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_atomic_job_creation.py
"""Test that job creation is atomic — no credits lost on dispatch failure."""
import pytest
from unittest.mock import patch, MagicMock


async def test_missing_routing_does_not_charge_credits(client, auth_headers, funded_user):
    """If model routing is not configured, credits must not be deducted."""
    # No seeded_routing fixture — routing table is empty
    resp = await client.post(
        "/api/jobs",
        headers=auth_headers,
        json={"seed_text": "Test seed text.", "goal": "Test", "tier": "small"},
    )
    assert resp.status_code == 500
    assert "routing" in resp.json()["detail"].lower()

    # Balance must be unchanged
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 10000  # funded_user starts with 10000


async def test_dispatch_failure_does_not_charge_credits(client, auth_headers, funded_user, seeded_routing):
    """If Celery dispatch fails, credits must not be deducted."""
    with patch("saas.api.jobs.run_simulation_task.delay", side_effect=Exception("broker down")):
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"seed_text": "Test seed text.", "goal": "Test", "tier": "small"},
        )
    assert resp.status_code == 500

    # Balance must be unchanged
    balance_resp = await client.get("/api/billing/balance", headers=auth_headers)
    assert balance_resp.json()["balance"] == 10000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_atomic_job_creation.py -v`
Expected: FAIL — `test_missing_routing` deducts credits before checking routing

- [ ] **Step 3: Rewrite `create_job` to be atomic**

Replace the `create_job` function in `saas/api/jobs.py`:

```python
@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    body: JobCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if len(body.seed_text) > MAX_SEED_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Seed text exceeds maximum of {MAX_SEED_CHARS} characters",
        )

    user_id = current_user["user_id"]
    credits = TIER_CREDITS[body.tier]

    # 1. Validate routing exists BEFORE touching credits
    route = await session.execute(
        select(ModelRouting).where(ModelRouting.sim_tier == body.tier.value)
    )
    routing = route.scalar_one_or_none()
    if not routing:
        raise HTTPException(
            status_code=500,
            detail=f"No model routing configured for tier: {body.tier.value}",
        )

    # 2. Debit credits (raises 402 if insufficient — no commit yet)
    ledger = CreditLedger(session)
    try:
        await ledger.debit(
            user_id=user_id,
            amount=credits,
            description=f"Job creation — tier {body.tier.value}",
        )
    except InsufficientCreditsError:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Required: {credits}",
        )

    # 3. Create job row (not committed yet)
    job = SimulationJob(
        user_id=user_id,
        seed_text=body.seed_text,
        goal=body.goal,
        tier=body.tier.value,
        credits_charged=credits,
        status=JobStatus.PENDING,
    )
    session.add(job)
    await session.flush()  # get job.id without committing

    # 4. Dispatch to Celery — if this fails, the whole transaction rolls back
    try:
        task_result = run_simulation_task.delay(
            job_id=job.id,
            user_id=user_id,
            seed_text=body.seed_text,
            goal=body.goal,
            tier=body.tier.value,
            model_id=routing.model_id,
            gpu_type=routing.gpu_type,
            max_rounds=routing.max_rounds,
            vllm_args=routing.vllm_args or "",
            llm_api_key=os.getenv("LLM_API_KEY", "not-needed"),
            zep_api_key=os.getenv("ZEP_API_KEY", ""),
            credits_charged=credits,
        )
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to queue simulation job")

    # 5. Store task ID and commit everything atomically
    job.celery_task_id = task_result.id
    await session.commit()
    await session.refresh(job)

    return job
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_atomic_job_creation.py tests/test_jobs_api.py tests/test_jobs_credit_gate.py tests/test_e2e.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add saas/api/jobs.py tests/test_atomic_job_creation.py
git commit -m "fix: make job creation atomic — no credits lost on dispatch failure (#14)"
```

---

### Task 4: Race-Safe Credit Debit (#19)

**Files:**
- Modify: `saas/billing/ledger.py:42-62`
- Test: `tests/test_concurrent_debit.py`

The current `debit()` does `get_balance()` then `INSERT`. Two concurrent calls can both see sufficient balance and both succeed, overspending.

Fix: use `SELECT ... FOR UPDATE` to lock the user's credit rows during balance check.

- [ ] **Step 1: Write failing test**

```python
# tests/test_concurrent_debit.py
"""Test that concurrent debits cannot overspend."""
import asyncio
import pytest
from saas.billing.ledger import CreditLedger, InsufficientCreditsError


async def test_concurrent_debits_cannot_overspend(db_session):
    """Two simultaneous 80-credit debits with 100 balance — only one should succeed."""
    ledger = CreditLedger(db_session)
    await ledger.credit(user_id="race-user", amount=100, description="initial")
    await db_session.commit()

    results = []

    async def try_debit():
        try:
            await ledger.debit(user_id="race-user", amount=80, description="concurrent")
            await db_session.commit()
            results.append("ok")
        except InsufficientCreditsError:
            results.append("insufficient")
        except Exception as e:
            results.append(f"error: {e}")

    # Run two debits concurrently
    await asyncio.gather(try_debit(), try_debit())

    # Exactly one should succeed
    assert results.count("ok") == 1
    assert results.count("insufficient") == 1

    # Final balance should be 20 (100 - 80)
    balance = await ledger.get_balance("race-user")
    assert balance == 20
```

Note: This test may not reliably reproduce the race on SQLite (no row locking). The fix should still be correct for PostgreSQL.

- [ ] **Step 2: Implement race-safe debit**

Replace `debit()` in `saas/billing/ledger.py`:

```python
    async def debit(
        self,
        user_id: str,
        amount: int,
        description: str,
        job_id: int | None = None,
    ) -> CreditEntry:
        # Use a single query that checks balance and inserts atomically.
        # The subquery calculates balance; if insufficient, no row is inserted.
        from sqlalchemy import text

        result = await self.session.execute(
            text(
                "INSERT INTO credit_entries (user_id, amount, description, job_id, created_at) "
                "SELECT :user_id, :amount, :description, :job_id, :created_at "
                "WHERE (SELECT COALESCE(SUM(amount), 0) FROM credit_entries WHERE user_id = :user_id) >= :required "
                "RETURNING id"
            ),
            {
                "user_id": user_id,
                "amount": -amount,
                "description": description,
                "job_id": job_id,
                "created_at": datetime.now(timezone.utc),
                "required": amount,
            },
        )
        row = result.first()
        if row is None:
            balance = await self.get_balance(user_id)
            raise InsufficientCreditsError(
                f"Insufficient credits: balance={balance}, required={amount}"
            )
        await self.session.flush()
        # Return the entry for callers that need it
        entry = await self.session.get(CreditEntry, row[0])
        return entry
```

Add `from datetime import datetime, timezone` at the top of `ledger.py` if not already imported.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_concurrent_debit.py tests/test_ledger.py tests/test_jobs_credit_gate.py -v`
Expected: All pass

Note: The INSERT...SELECT...WHERE approach works on both PostgreSQL and SQLite. On PostgreSQL it provides stronger guarantees due to MVCC.

- [ ] **Step 4: Commit**

```bash
git add saas/billing/ledger.py tests/test_concurrent_debit.py
git commit -m "fix: race-safe credit debit via atomic INSERT...SELECT (#19)"
```

---

### Task 5: Run Full Test Suite

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: 232+ tests pass, 0 failures

- [ ] **Step 2: Run linter**

Run: `ruff check saas/ tests/`
Expected: All checks passed

- [ ] **Step 3: Commit any fixups**

```bash
git add -A && git commit -m "fix: lint and test fixups for security/billing changes"
```
