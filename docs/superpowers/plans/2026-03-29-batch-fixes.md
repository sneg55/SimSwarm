# Batch Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 13 open issues spanning critical bugs, refactoring, UX features, and cleanup.

**Architecture:** Sequential implementation grouped by dependency. Backend fixes first (critical bugs, refactoring), then API+frontend features (pagination, profile, credit packs, error monitoring, skeletons), then cleanup (unused components, composables).

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, Vue 3 Composition API, Tailwind CSS, Pinia

---

## Task 1: Idempotent refunds (#30)

**Files:**
- Modify: `saas/workers/refund.py`
- Modify: `saas/workers/recovery.py`
- Test: `tests/test_refund_idempotency.py`

- [ ] **Step 1: Write failing test for duplicate refund prevention**

```python
# tests/test_refund_idempotency.py
"""Tests that refund logic is idempotent — calling twice for the same job doesn't double-credit."""
import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_duplicate_refund_does_not_stack(db_session, funded_user):
    """Refunding the same job_id twice should only insert one credit entry."""
    user_id = funded_user["user_id"]
    job_id = 9999

    # Debit first
    await db_session.execute(
        text("INSERT INTO credit_entries (user_id, amount, description, job_id) "
             "VALUES (:uid, -30, 'test charge', :jid)"),
        {"uid": user_id, "jid": job_id},
    )
    await db_session.commit()

    from saas.workers.refund import _refund_credits

    # Call refund twice
    _refund_credits(job_id, user_id, 30)
    _refund_credits(job_id, user_id, 30)

    result = await db_session.execute(
        text("SELECT COUNT(*) FROM credit_entries WHERE job_id = :jid AND amount > 0"),
        {"jid": job_id},
    )
    count = result.scalar()
    assert count == 1, f"Expected 1 refund entry, got {count}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_refund_idempotency.py -v`
Expected: FAIL — second refund creates duplicate entry

- [ ] **Step 3: Add idempotency guard to _refund_credits**

In `saas/workers/refund.py`, before the INSERT, check if a positive credit entry already exists for this job_id:

```python
async def _do_refund():
    async with factory() as session:
        try:
            # Idempotency check: skip if refund already exists for this job
            existing = await session.execute(
                text("SELECT 1 FROM credit_entries WHERE job_id = :jid AND amount > 0 LIMIT 1"),
                {"jid": job_id},
            )
            if existing.first():
                logger.info("Refund already exists for job %d — skipping duplicate", job_id)
                return

            await session.execute(
                text(
                    "INSERT INTO credit_entries (user_id, amount, description, job_id, created_at) "
                    "VALUES (:user_id, :amount, :description, :job_id, :created_at)"
                ),
                {
                    "user_id": user_id,
                    "amount": credits,
                    "description": f"Refund: job {job_id} failed",
                    "job_id": job_id,
                    "created_at": datetime.now(timezone.utc),
                },
            )
            await session.commit()
            logger.info("Refunded %d credits for job %d to user %s", credits, job_id, user_id)
        except Exception as exc:
            logger.warning("Could not refund credits for job %d: %s", job_id, exc)
```

Also add the same guard to `recovery.py` line 177 — the recovery refund INSERT should check `WHERE NOT EXISTS (SELECT 1 FROM credit_entries WHERE job_id = :jid AND amount > 0)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_refund_idempotency.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add saas/workers/refund.py saas/workers/recovery.py tests/test_refund_idempotency.py
git commit -m "fix: make refunds idempotent — skip duplicate credit entries per job_id (#30)"
```

---

## Task 2: Resume teardown without in-memory map (#31)

**Files:**
- Modify: `saas/gpu/failover.py`
- Modify: `saas/workers/persistence.py`
- Test: `tests/test_failover.py` (add test)

- [ ] **Step 1: Write failing test for teardown with empty ownership map**

```python
# Add to tests/test_failover.py
@pytest.mark.asyncio
async def test_terminate_falls_back_to_runpod_when_map_empty():
    """Terminate should use RunPod directly when _active_instances map is empty."""
    primary = AsyncMock(spec=GPUProvider)
    fallback = AsyncMock(spec=GPUProvider)
    failover = FailoverGPUProvider(primary, fallback)

    # Don't register instance — simulates worker restart
    await failover.terminate("orphan-pod", provider_hint="runpod")

    primary.terminate.assert_called_once_with("orphan-pod")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_failover.py::test_terminate_falls_back_to_runpod_when_map_empty -v`
Expected: FAIL — terminate() doesn't accept provider_hint

- [ ] **Step 3: Add provider_hint fallback to FailoverGPUProvider.terminate**

In `saas/gpu/failover.py`:

```python
async def terminate(self, instance_id: str, provider_hint: str | None = None) -> None:
    """Delegate termination to the provider that created the instance.

    Falls back to provider_hint when the in-memory ownership map is empty
    (e.g., after worker restart).
    """
    provider = self._active_instances.get(instance_id)
    if provider:
        await provider.terminate(instance_id)
        del self._active_instances[instance_id]
    elif provider_hint:
        # Fallback: use hint from persisted job.gpu_provider
        target = self.primary if provider_hint == "runpod" else self.fallback
        await target.terminate(instance_id)
        logger.info("Terminated %s via provider_hint=%s (no ownership map)", instance_id, provider_hint)
    else:
        # Last resort: try primary (RunPod is default)
        logger.warning("No ownership map or hint for %s — trying primary provider", instance_id)
        await self.primary.terminate(instance_id)
```

- [ ] **Step 4: Persist gpu_provider on provisioning**

In `saas/workers/persistence.py`, update `_async_update_pod_id` to also set `gpu_provider`:

```python
async def _async_update_pod_id(job_id: int, pod_id: str, gpu_provider: str = "runpod") -> None:
    # ... existing code ...
    await session.execute(
        text(
            "UPDATE simulation_jobs SET pod_id = :pod_id, status = 'PROVISIONING', "
            "gpu_provider = :gpu_provider WHERE id = :job_id"
        ),
        {"pod_id": pod_id, "gpu_provider": gpu_provider, "job_id": job_id},
    )
```

Update callers in `job_runner.py` to pass the provider name through callbacks.

- [ ] **Step 5: Use gpu_provider in recovery.py terminate call**

In `saas/workers/recovery.py` line ~145, when terminating orphaned pods, read `gpu_provider` from the job row and pass it:

```python
if pod_id and pod_alive and runpod_key:
    try:
        import runpod
        runpod.api_key = runpod_key
        runpod.terminate_pod(pod_id)
        logger.info("recover.terminated_pod job_id=%d pod_id=%s", job_id, pod_id)
    except Exception as term_exc:
        logger.warning("recover.terminate_failed job_id=%d error=%s", job_id, term_exc)
```

(Recovery already uses RunPod directly, which is correct since that's the only provider currently in production.)

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_failover.py tests/test_cleanup.py -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add saas/gpu/failover.py saas/workers/persistence.py tests/test_failover.py
git commit -m "fix: persist gpu_provider, use fallback in terminate after restart (#31)"
```

---

## Task 3: Remove global settings access (#35)

**Files:**
- Modify: `saas/api/billing.py`
- Modify: `saas/main.py`

- [ ] **Step 1: Replace _app_settings import with request.app.state.settings**

In `saas/api/billing.py`, the `_get_stripe_service()` helper imports `_app_settings` from main. Replace with a function that takes settings as a parameter, injected via FastAPI dependency:

```python
def _get_stripe_service(request: Request) -> StripeService:
    settings = request.app.state.settings
    return StripeService(
        secret_key=settings.STRIPE_SECRET_KEY,
        webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
    )
```

Update all callers in billing.py to pass `request` through.

- [ ] **Step 2: Remove _app_settings from main.py**

Delete the global `_app_settings` variable and its assignment. `app.state.settings` is the single source of truth.

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add saas/api/billing.py saas/main.py
git commit -m "refactor: remove global _app_settings, use request.app.state.settings (#35)"
```

---

## Task 4: Move sentiment backfill out of GET endpoints (#36)

**Files:**
- Modify: `saas/api/jobs.py`
- Modify: `saas/api/share.py`

- [ ] **Step 1: Remove side-effect from GET /jobs/{id}/graph**

In `saas/api/jobs.py`, the graph GET endpoint calls `score_entity_sentiment()` and commits. Remove the write — return data as-is. Sentiment is already scored during the pipeline in `run_job.py`.

- [ ] **Step 2: Remove side-effect from GET /share/{token} and /share/{token}/graph**

Same pattern in `saas/api/share.py`. Remove `needs_sentiment_backfill` check and `session.commit()` from GET endpoints.

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add saas/api/jobs.py saas/api/share.py
git commit -m "refactor: remove sentiment backfill side-effects from GET endpoints (#36)"
```

---

## Task 5: Centralize tier/timeout constants (#38)

**Files:**
- Create: `saas/tiers.py`
- Modify: `saas/workers/job_runner.py`
- Modify: `saas/schemas/jobs.py`

- [ ] **Step 1: Create saas/tiers.py with all tier constants**

```python
"""Centralized tier configuration — single source of truth for all tier-related constants."""

TIER_CREDITS = {"small": 30, "medium": 90, "large": 300}

TIER_TIMEOUTS = {"small": 2700, "medium": 18000, "large": 43200}

TIER_MAX_COST_USD = {"small": 1.50, "medium": 4.00, "large": 8.00}

VALID_TIERS = frozenset(TIER_CREDITS.keys())
```

- [ ] **Step 2: Update imports in job_runner.py and schemas/jobs.py**

Replace local definitions with imports from `saas.tiers`.

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add saas/tiers.py saas/workers/job_runner.py saas/schemas/jobs.py
git commit -m "refactor: centralize tier constants in saas/tiers.py (#38)"
```

---

## Task 6: Offload CPU-heavy work from API path (#39)

**Files:**
- Modify: `saas/api/jobs.py`
- Modify: `saas/api/share.py`

- [ ] **Step 1: Identify CPU-heavy operations in request path**

The main offenders are JSON parsing of large `result_graph` and `result_chat_log` fields in the graph endpoints. These are already stored as JSON strings — avoid parsing and re-serializing when possible.

For the graph endpoint: return the raw JSON string via `Response(content=job.result_graph, media_type="application/json")` instead of parsing into Python dict and letting Pydantic re-serialize.

- [ ] **Step 2: Optimize graph endpoints to avoid double-serialization**

```python
from fastapi.responses import Response

@router.get("/{job_id}/graph")
async def get_job_graph(job_id: int, ...):
    job = await session.get(SimulationJob, job_id)
    # ... auth checks ...
    if not job.result_graph:
        raise HTTPException(status_code=404, detail="Graph not available")
    return Response(content=job.result_graph, media_type="application/json")
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add saas/api/jobs.py saas/api/share.py
git commit -m "perf: return raw JSON for graph endpoints, skip double-serialization (#39)"
```

---

## Task 7: Jobs list summary endpoint + pagination (#34 + #49)

**Files:**
- Modify: `saas/api/jobs.py`
- Modify: `saas/schemas/jobs.py`
- Modify: `frontend/src/api/jobs.js`
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Step 1: Add JobSummary schema (no large text fields)**

In `saas/schemas/jobs.py`:

```python
class JobSummary(BaseModel):
    id: int
    goal: str
    tier: str
    credits_charged: int
    status: str
    pipeline_stage: int | None
    key_insight: str | None = None
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    jobs: list[JobSummary]
    total: int
    page: int
    per_page: int
```

- [ ] **Step 2: Update GET /jobs endpoint with pagination**

In `saas/api/jobs.py`:

```python
@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = 1,
    per_page: int = 10,
    status: str | None = None,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = current_user["user_id"]
    query = select(SimulationJob).where(SimulationJob.user_id == user_id)

    if status:
        query = query.where(SimulationJob.status == status)

    # Count total
    from sqlalchemy import func
    count_q = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_q)).scalar()

    # Paginate
    query = query.order_by(SimulationJob.created_at.desc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await session.execute(query)
    jobs = result.scalars().all()

    return JobListResponse(jobs=jobs, total=total, page=page, per_page=per_page)
```

- [ ] **Step 3: Update frontend API client**

In `frontend/src/api/jobs.js`:

```javascript
export async function listJobs(page = 1, perPage = 10, status = null) {
  const params = { page, per_page: perPage }
  if (status) params.status = status
  const response = await api.get('/jobs', { params })
  return response.data
}
```

- [ ] **Step 4: Add pagination to Dashboard.vue**

Add page state, load more button, update the job loading logic:

```javascript
const page = ref(1)
const totalJobs = ref(0)
const hasMore = computed(() => jobs.value.length < totalJobs.value)

async function loadJobs(append = false) {
  const data = await listJobs(page.value)
  if (append) {
    jobs.value = [...jobs.value, ...data.jobs]
  } else {
    jobs.value = data.jobs
  }
  totalJobs.value = data.total
}

function loadMore() {
  page.value++
  loadJobs(true)
}
```

Add a "Load more" button at the bottom of the job list.

- [ ] **Step 5: Run tests**

Run: `pytest tests/ -x -q && cd frontend && npm test -- --run`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add saas/api/jobs.py saas/schemas/jobs.py frontend/src/api/jobs.js frontend/src/views/Dashboard.vue
git commit -m "feat: paginated jobs list with summary schema, load more in dashboard (#34, #49)"
```

---

## Task 8: User profile/settings page (#50)

**Files:**
- Create: `saas/api/profile.py`
- Modify: `saas/main.py` (register router)
- Modify: `frontend/src/views/Account.vue`

- [ ] **Step 1: Add password change endpoint**

In `saas/api/profile.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.auth.dependencies import get_current_user
from saas.auth.password import verify_password, hash_password

router = APIRouter(prefix="/profile", tags=["profile"])


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.put("/password")
async def change_password(
    body: PasswordChange,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    result = await session.execute(
        text("SELECT password_hash FROM users WHERE id = :uid"),
        {"uid": current_user["user_id"]},
    )
    row = result.first()
    if not row or not verify_password(body.current_password, row[0]):
        raise HTTPException(status_code=403, detail="Current password is incorrect")

    new_hash = hash_password(body.new_password)
    await session.execute(
        text("UPDATE users SET password_hash = :hash WHERE id = :uid"),
        {"hash": new_hash, "uid": current_user["user_id"]},
    )
    await session.commit()
    return {"status": "ok"}


@router.delete("/account")
async def delete_account(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    uid = current_user["user_id"]
    # Soft-delete: set email to deleted_<id>@deleted and clear password
    await session.execute(
        text("UPDATE users SET email = :email, password_hash = '' WHERE id = :uid"),
        {"email": f"deleted_{uid}@deleted", "uid": uid},
    )
    await session.commit()
    return {"status": "deleted"}
```

- [ ] **Step 2: Register router in main.py**

Add `from saas.api.profile import router as profile_router` and include it in the api_router.

- [ ] **Step 3: Add settings UI to Account.vue**

Add a "Settings" section below transaction history with:
- Password change form (current + new + confirm)
- Delete account button with confirmation dialog

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -x -q && cd frontend && npm test -- --run`

- [ ] **Step 5: Commit**

```bash
git add saas/api/profile.py saas/main.py frontend/src/views/Account.vue
git commit -m "feat: password change and account deletion in profile settings (#50)"
```

---

## Task 9: Skeleton loading screens (#46)

**Files:**
- Create: `frontend/src/components/SkeletonCard.vue`
- Modify: `frontend/src/views/Dashboard.vue`
- Modify: `frontend/src/views/SimulationStatus.vue`
- Modify: `frontend/src/views/Account.vue`

- [ ] **Step 1: Create reusable SkeletonCard component**

```vue
<template>
  <div class="animate-pulse bg-ocean-deep border border-mist-depth rounded-2xl p-5 space-y-3">
    <div class="h-4 bg-mist-depth rounded w-3/4" />
    <div class="h-3 bg-mist-depth/60 rounded w-1/2" />
    <div v-if="lines > 0" class="space-y-2 mt-4">
      <div v-for="i in lines" :key="i" class="h-3 bg-mist-depth/40 rounded" :style="{ width: (90 - i * 10) + '%' }" />
    </div>
  </div>
</template>

<script setup>
defineProps({ lines: { type: Number, default: 2 } })
</script>
```

- [ ] **Step 2: Replace "Loading..." text in Dashboard, SimulationStatus, Account**

Replace each `<div>Loading...</div>` with `<div class="space-y-4"><SkeletonCard v-for="i in 3" :key="i" /></div>` (adjusted per view).

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend && npm test -- --run`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/SkeletonCard.vue frontend/src/views/Dashboard.vue frontend/src/views/SimulationStatus.vue frontend/src/views/Account.vue
git commit -m "feat: skeleton loading screens replace plain Loading text (#46)"
```

---

## Task 10: DB-configurable credit packs (#47)

**Files:**
- Create: `saas/models/credit_pack.py`
- Create: `alembic/versions/xxx_add_credit_packs_table.py`
- Modify: `saas/api/billing.py`
- Modify: `saas/billing/credit_packs.py`
- Modify: `frontend/src/views/Account.vue`
- Modify: `frontend/src/api/billing.js` (or similar)

- [ ] **Step 1: Create CreditPack model**

```python
# saas/models/credit_pack.py
from sqlalchemy import String, Integer, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from saas.database import Base


class CreditPack(Base):
    __tablename__ = "credit_packs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))
    credits: Mapped[int] = mapped_column(Integer)
    price_cents: Mapped[int] = mapped_column(Integer)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
```

- [ ] **Step 2: Create Alembic migration seeded with current packs**

```bash
alembic revision --autogenerate -m "add credit_packs table"
```

Add seed data in the upgrade() function with the 3 current packs.

- [ ] **Step 3: Add GET /api/billing/packs endpoint**

```python
@router.get("/packs")
async def list_packs(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(CreditPackModel).where(CreditPackModel.active == True).order_by(CreditPackModel.sort_order)
    )
    return [{"name": p.name, "credits": p.credits, "price_cents": p.price_cents,
             "description": p.description} for p in result.scalars()]
```

- [ ] **Step 4: Update Account.vue to fetch packs from API instead of hardcoding**

Replace the hardcoded pack array with an API fetch on mount.

- [ ] **Step 5: Run tests**

Run: `pytest tests/ -x -q && cd frontend && npm test -- --run`

- [ ] **Step 6: Commit**

```bash
git add saas/models/credit_pack.py alembic/versions/ saas/api/billing.py saas/billing/credit_packs.py frontend/src/views/Account.vue
git commit -m "feat: DB-configurable credit packs with API endpoint (#47)"
```

---

## Task 11: Error monitoring - Layer 1 capture (#45)

**Files:**
- Create: `saas/models/error_event.py`
- Create: `saas/middleware/error_tracking.py`
- Create: `alembic/versions/xxx_add_error_events_table.py`
- Modify: `saas/main.py`
- Modify: `saas/workers/celery_app.py`

- [ ] **Step 1: Create ErrorEvent model**

```python
# saas/models/error_event.py
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from saas.database import Base


class ErrorEvent(Base):
    __tablename__ = "error_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    level: Mapped[str] = mapped_column(String(20), default="ERROR")
    source: Mapped[str] = mapped_column(String(20))  # api, worker, gpu
    message: Mapped[str] = mapped_column(Text)
    traceback: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
```

- [ ] **Step 2: Create error tracking middleware**

```python
# saas/middleware/error_tracking.py
import traceback as tb
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class ErrorTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Log to error_events table
            from saas.models.error_event import ErrorEvent
            from saas.database import get_session_factory

            try:
                factory = get_session_factory()
                async with factory() as session:
                    event = ErrorEvent(
                        source="api",
                        message=str(exc)[:4096],
                        traceback=tb.format_exc()[:8192],
                        request_path=str(request.url.path)[:500],
                    )
                    session.add(event)
                    await session.commit()
            except Exception:
                pass  # Don't let error tracking break the app
            raise
```

- [ ] **Step 3: Create migration**

```bash
alembic revision --autogenerate -m "add error_events table"
```

- [ ] **Step 4: Register middleware and add Celery task failure handler**

In `saas/main.py`, add the middleware. In `saas/workers/celery_app.py`, add a `task_failure` signal handler that writes to the same table.

- [ ] **Step 5: Add beat task for auto-pruning (30 days)**

Add to beat_schedule in celery_app.py:

```python
"prune-error-events": {
    "task": "fishcloud.prune_error_events",
    "schedule": 86400.0,  # daily
},
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/ -x -q`

- [ ] **Step 7: Commit**

```bash
git add saas/models/error_event.py saas/middleware/error_tracking.py alembic/versions/ saas/main.py saas/workers/celery_app.py
git commit -m "feat: error event capture middleware + Celery failure handler (#45)"
```

---

## Task 12: Remove unused frontend components (#41)

**Files:**
- Delete: `frontend/src/components/TierSelector.vue`
- Delete: `frontend/src/components/ExportButtons.vue`
- Delete: `frontend/src/components/NavbarNew.vue`
- Delete: `frontend/src/components/SeedUploader.vue`
- Delete: `frontend/src/components/ViewModeToggle.vue`
- Delete: `frontend/src/components/wizard/SeedTips.vue`
- Delete: associated test files if any

- [ ] **Step 1: Verify each component has zero imports**

Run grep for each component name across all `.vue` and `.js` files. Confirm zero hits (excluding test files).

- [ ] **Step 2: Delete unused components and their tests**

```bash
rm frontend/src/components/TierSelector.vue
rm frontend/src/components/ExportButtons.vue
rm frontend/src/components/NavbarNew.vue
rm frontend/src/components/SeedUploader.vue
rm frontend/src/components/ViewModeToggle.vue
rm frontend/src/components/wizard/SeedTips.vue
rm -f tests/components/TierSelector.spec.js
rm -f src/components/__tests__/ExportButtons.spec.js
```

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend && npm test -- --run`
Expected: Remaining tests pass (deleted test files won't run)

- [ ] **Step 4: Commit**

```bash
git add -A frontend/src/components/ frontend/tests/
git commit -m "chore: remove 6 unused legacy frontend components (#41)"
```

---

## Task 13: Extract result-view composables (#37)

**Files:**
- Create: `frontend/src/composables/useSimulationData.js`
- Modify: `frontend/src/views/SimulationResults.vue`
- Modify: `frontend/src/views/SharedResult.vue`

- [ ] **Step 1: Create useSimulationData composable**

```javascript
// frontend/src/composables/useSimulationData.js
import { computed } from 'vue'

export function useSimulationData(job) {
  const chatLog = computed(() => {
    if (!job.value) return []
    try {
      const raw = job.value.result_chat_log || job.value.chat_log || '[]'
      const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
      return Array.isArray(parsed) ? parsed : []
    } catch { return [] }
  })

  const chatMessages = computed(() => {
    return chatLog.value
      .map(entry => {
        if (entry.content && entry.role) return entry
        return {
          role: 'assistant',
          agent: entry.agent_name || entry.agent || 'Agent',
          content: entry.action_args?.content || entry.content || JSON.stringify(entry.action_args || {}),
          timestamp: entry.timestamp || null,
        }
      })
      .filter(m => m.content)
  })

  const structured = computed(() => {
    if (!job.value?.result_structured) return null
    try {
      return typeof job.value.result_structured === 'string'
        ? JSON.parse(job.value.result_structured)
        : job.value.result_structured
    } catch { return null }
  })

  const sentimentBars = computed(() => {
    if (!structured.value?.sentiment) return []
    return structured.value.sentiment.map(s => ({
      label: s.label,
      width: s.value,
      value: `${s.value}%`,
      gradient: s.direction === 'positive'
        ? 'linear-gradient(90deg, #22D3EE, #6EE7B7)'
        : 'linear-gradient(90deg, #FF6B6B, #F97316)',
      valueColor: s.direction === 'positive' ? '#6EE7B7' : '#FF6B6B',
    }))
  })

  function buildNodeRelationships(nodes, edges) {
    const nameMap = Object.fromEntries(nodes.map(n => [n.uuid, n.name || n.uuid]))
    const relMap = {}
    for (const edge of edges) {
      const src = edge.source_node_uuid
      const tgt = edge.target_node_uuid
      if (!relMap[src]) relMap[src] = []
      if (!relMap[tgt]) relMap[tgt] = []
      relMap[src].push({
        direction: 'outgoing',
        target_uuid: tgt,
        targetName: nameMap[tgt] || tgt,
        type: edge.name || edge.fact || '',
      })
      relMap[tgt].push({
        direction: 'incoming',
        source_uuid: src,
        sourceName: nameMap[src] || src,
        type: edge.name || edge.fact || '',
      })
    }
    return nodes.map(n => ({ ...n, relationships: relMap[n.uuid] || [] }))
  }

  return { chatLog, chatMessages, structured, sentimentBars, buildNodeRelationships }
}
```

- [ ] **Step 2: Refactor SimulationResults.vue to use composable**

Replace inline computed properties with `const { chatLog, chatMessages, structured, sentimentBars, buildNodeRelationships } = useSimulationData(job)`.

- [ ] **Step 3: Refactor SharedResult.vue similarly**

Same extraction for any duplicated data shaping logic.

- [ ] **Step 4: Run frontend tests**

Run: `cd frontend && npm test -- --run`

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSimulationData.js frontend/src/views/SimulationResults.vue frontend/src/views/SharedResult.vue
git commit -m "refactor: extract simulation data shaping into useSimulationData composable (#37)"
```
