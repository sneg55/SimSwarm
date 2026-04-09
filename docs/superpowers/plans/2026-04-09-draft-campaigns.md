# Draft Campaigns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users save incomplete simulation wizard progress as drafts and resume later.

**Architecture:** Add `DRAFT` status to `SimulationJob`, three new API endpoints (create draft, update draft, launch draft), and modify the frontend wizard to auto-save on step transitions. Credits are only deducted at launch.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, Vue 3 Composition API, Pinia, pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-04-09-draft-campaigns-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `saas/jobs/models.py` | Modify | Add `DRAFT` to JobStatus enum, make `goal`/`tier` nullable |
| `saas/jobs/schemas.py` | Modify | Add `DraftCreate`, `DraftUpdate` schemas; make `goal`/`tier` optional in responses |
| `saas/jobs/api_draft.py` | Create | Draft endpoints: create, update, launch |
| `saas/jobs/api.py` | Modify | Include draft sub-router |
| `tests/test_drafts.py` | Create | All backend draft tests |
| `frontend/src/api/jobs.js` | Modify | Add `createDraft`, `updateDraft`, `launchDraft` functions |
| `frontend/src/views/NewSimulation.vue` | Modify | Auto-save on step transitions, resume from draft |
| `frontend/src/views/DashboardView.vue` | Modify | Drafts section above active jobs |
| Alembic migration | Create | `goal`/`tier` nullable + DRAFT status |

---

### Task 1: Add DRAFT status and make columns nullable

**Files:**
- Modify: `saas/jobs/models.py:8-15` (JobStatus enum)
- Modify: `saas/jobs/models.py:23-24` (goal, tier columns)

- [ ] **Step 1: Add DRAFT to JobStatus enum**

In `saas/jobs/models.py`, change the enum at line 8:

```python
class JobStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    PROVISIONING = "PROVISIONING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
```

- [ ] **Step 2: Make goal and tier nullable**

In `saas/jobs/models.py`, change lines 23-24:

```python
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    tier: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

- [ ] **Step 3: Make goal and tier optional in response schemas**

In `saas/jobs/schemas.py`, change `JobResponse` (line 35) and `JobSummary` (line 58):

```python
# In JobResponse (line 35):
    goal: str | None = None
    tier: str | None = None

# In JobSummary (line 58):
    goal: str | None = None
    tier: str | None = None
```

- [ ] **Step 4: Generate Alembic migration**

Run:
```bash
cd /Users/sneg55/Documents/GitHub/fishandcat
alembic revision --autogenerate -m "add DRAFT status, nullable goal and tier"
```

Review the generated migration. It should contain:
- ALTER `goal` column to nullable
- ALTER `tier` column to nullable
- The DRAFT enum value will work automatically since `JobStatus` is a Python enum stored as a string (not a PostgreSQL ENUM type)

- [ ] **Step 5: Commit**

```bash
git add saas/jobs/models.py saas/jobs/schemas.py alembic/versions/
git commit -m "feat: add DRAFT status, make goal/tier nullable (#68)"
```

---

### Task 2: Create DraftCreate and DraftUpdate schemas

**Files:**
- Modify: `saas/jobs/schemas.py`

- [ ] **Step 1: Add DraftCreate schema**

In `saas/jobs/schemas.py`, add after the `JobCreate` class (after line 29):

```python
class DraftCreate(BaseModel):
    seed_text: str = ""
    goal: str | None = None
    tier: TierEnum | None = None
    enrich_web: bool = True
    forecast_days: int | None = None
```

No `seed_not_empty` validator — drafts allow empty seed_text at creation (though step 1 will always provide it).

- [ ] **Step 2: Add DraftUpdate schema**

Add after `DraftCreate`:

```python
class DraftUpdate(BaseModel):
    seed_text: str | None = None
    goal: str | None = None
    tier: TierEnum | None = None
    enrich_web: bool | None = None
    forecast_days: int | None = None
```

All fields optional — only provided fields are updated.

- [ ] **Step 3: Commit**

```bash
git add saas/jobs/schemas.py
git commit -m "feat: add DraftCreate and DraftUpdate schemas (#68)"
```

---

### Task 3: Write failing tests for draft endpoints

**Files:**
- Create: `tests/test_drafts.py`

- [ ] **Step 1: Write all draft endpoint tests**

Create `tests/test_drafts.py`:

```python
"""Tests for draft campaign endpoints."""
import pytest
from unittest.mock import patch


SEED = "A" * 600  # Minimum valid seed length


class TestCreateDraft:
    async def test_create_draft_with_seed(self, client, auth_headers):
        resp = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED, "enrich_web": True},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "DRAFT"
        assert data["seed_text"] == SEED
        assert data["goal"] is None
        assert data["tier"] is None
        assert data["credits_charged"] == 0

    async def test_create_draft_empty_body(self, client, auth_headers):
        resp = await client.post(
            "/api/jobs/draft",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "DRAFT"
        assert data["seed_text"] == ""

    async def test_create_draft_requires_auth(self, client):
        resp = await client.post("/api/jobs/draft", json={"seed_text": SEED})
        assert resp.status_code == 401


class TestUpdateDraft:
    async def test_update_goal(self, client, auth_headers):
        # Create draft first
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        resp = await client.patch(
            f"/api/jobs/draft/{draft_id}",
            json={"goal": "Predict market impact"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["goal"] == "Predict market impact"

    async def test_update_tier(self, client, auth_headers):
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        resp = await client.patch(
            f"/api/jobs/draft/{draft_id}",
            json={"tier": "small"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["tier"] == "small"

    async def test_update_non_draft_returns_409(self, client, auth_headers, db_session):
        """Cannot update a job that is not in DRAFT status."""
        from saas.jobs.models import SimulationJob, JobStatus

        job = SimulationJob(
            user_id=auth_headers["_user_id"],
            seed_text=SEED,
            goal="test",
            tier="small",
            credits_charged=30,
            status=JobStatus.PENDING,
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        resp = await client.patch(
            f"/api/jobs/draft/{job.id}",
            json={"goal": "new goal"},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    async def test_update_other_users_draft_returns_404(self, client, auth_headers):
        resp = await client.patch(
            "/api/jobs/draft/99999",
            json={"goal": "new goal"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_update_seed_text_too_long(self, client, auth_headers):
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        resp = await client.patch(
            f"/api/jobs/draft/{draft_id}",
            json={"seed_text": "A" * 60000},
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestLaunchDraft:
    @patch("saas.jobs.api_draft.run_simulation_task")
    async def test_launch_complete_draft(
        self, mock_task, client, auth_headers, funded_user, seeded_routing
    ):
        mock_task.delay.return_value.id = "fake-celery-id"

        # Create and fill draft
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        await client.patch(
            f"/api/jobs/draft/{draft_id}",
            json={"goal": "Predict impact", "tier": "small"},
            headers=auth_headers,
        )

        # Launch
        resp = await client.post(
            f"/api/jobs/draft/{draft_id}/launch",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["credits_charged"] == 30
        mock_task.delay.assert_called_once()

    async def test_launch_incomplete_draft_returns_422(self, client, auth_headers):
        """Draft missing goal cannot be launched."""
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        resp = await client.post(
            f"/api/jobs/draft/{draft_id}/launch",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    @patch("saas.jobs.api_draft.run_simulation_task")
    async def test_launch_insufficient_credits_returns_402(
        self, mock_task, client, auth_headers, seeded_routing
    ):
        """User with 0 credits cannot launch."""
        mock_task.delay.return_value.id = "fake-celery-id"

        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]
        await client.patch(
            f"/api/jobs/draft/{draft_id}",
            json={"goal": "Predict impact", "tier": "small"},
            headers=auth_headers,
        )

        resp = await client.post(
            f"/api/jobs/draft/{draft_id}/launch",
            headers=auth_headers,
        )
        assert resp.status_code == 402

    async def test_launch_non_draft_returns_409(self, client, auth_headers, db_session):
        from saas.jobs.models import SimulationJob, JobStatus

        job = SimulationJob(
            user_id=auth_headers["_user_id"],
            seed_text=SEED,
            goal="test",
            tier="small",
            credits_charged=30,
            status=JobStatus.COMPLETED,
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)

        resp = await client.post(
            f"/api/jobs/draft/{job.id}/launch",
            headers=auth_headers,
        )
        assert resp.status_code == 409


class TestListIncludesDrafts:
    async def test_drafts_appear_in_job_list(self, client, auth_headers):
        await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )

        resp = await client.get("/api/jobs", headers=auth_headers)
        assert resp.status_code == 200
        jobs = resp.json()["jobs"]
        assert len(jobs) == 1
        assert jobs[0]["status"] == "DRAFT"


class TestDeleteDraft:
    async def test_delete_draft(self, client, auth_headers):
        create = await client.post(
            "/api/jobs/draft",
            json={"seed_text": SEED},
            headers=auth_headers,
        )
        draft_id = create.json()["id"]

        resp = await client.delete(f"/api/jobs/{draft_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify gone
        resp = await client.get(f"/api/jobs/{draft_id}", headers=auth_headers)
        assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
pytest tests/test_drafts.py -v
```

Expected: All tests FAIL (404 on `/api/jobs/draft` — endpoint doesn't exist yet).

- [ ] **Step 3: Commit**

```bash
git add tests/test_drafts.py
git commit -m "test: add draft campaign endpoint tests (#68)"
```

---

### Task 4: Implement draft API endpoints

**Files:**
- Create: `saas/jobs/api_draft.py`
- Modify: `saas/jobs/api.py:19-20` (include sub-router)

- [ ] **Step 1: Create api_draft.py with all three endpoints**

Create `saas/jobs/api_draft.py`:

```python
"""Draft campaign API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.jobs.models import SimulationJob, JobStatus, ModelRouting
from saas.jobs.schemas import DraftCreate, DraftUpdate, JobResponse
from saas.constants.tiers import TIER_CREDITS
from saas.billing.ledger import CreditLedger, InsufficientCreditsError
from saas.auth.dependencies import get_current_user
from saas.storage.minio_client import SimDataStorage
from saas.jobs.tasks import run_simulation_task

import os

router = APIRouter(prefix="/draft", tags=["drafts"])


def _get_sim_data_storage(request: Request) -> SimDataStorage:
    settings = request.app.state.settings
    return SimDataStorage(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        bucket=settings.MINIO_BUCKET,
        secure=settings.MINIO_SECURE,
        proxy_base=settings.MINIO_PROXY_BASE,
    )


async def _get_user_draft(
    job_id: int, user_id: str, session: AsyncSession
) -> SimulationJob:
    """Fetch a draft owned by the user, or raise 404/409."""
    job = await session.get(SimulationJob, job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Draft not found")
    if job.status != JobStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Job is not a draft")
    return job


@router.post("", response_model=JobResponse, status_code=201)
async def create_draft(
    body: DraftCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new draft with partial data. No credit check."""
    job = SimulationJob(
        user_id=current_user["user_id"],
        seed_text=body.seed_text,
        goal=body.goal,
        tier=body.tier.value if body.tier else None,
        credits_charged=0,
        status=JobStatus.DRAFT,
        enrich_web=body.enrich_web,
        forecast_days=body.forecast_days,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


@router.patch("/{job_id}", response_model=JobResponse)
async def update_draft(
    job_id: int,
    body: DraftUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update an existing draft. Only works when status == DRAFT."""
    job = await _get_user_draft(job_id, current_user["user_id"], session)

    max_seed_chars = request.app.state.settings.MAX_SEED_CHARS
    if body.seed_text is not None:
        if len(body.seed_text) > max_seed_chars:
            raise HTTPException(
                status_code=400,
                detail=f"Seed text exceeds maximum of {max_seed_chars} characters",
            )
        job.seed_text = body.seed_text
    if body.goal is not None:
        job.goal = body.goal
    if body.tier is not None:
        job.tier = body.tier.value
    if body.enrich_web is not None:
        job.enrich_web = body.enrich_web
    if body.forecast_days is not None:
        job.forecast_days = body.forecast_days

    await session.commit()
    await session.refresh(job)
    return job


@router.post("/{job_id}/launch", response_model=JobResponse)
async def launch_draft(
    job_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Launch a complete draft: validate, debit credits, dispatch to Celery."""
    user_id = current_user["user_id"]
    job = await _get_user_draft(job_id, user_id, session)

    # 1. Validate completeness
    missing = []
    if not job.seed_text or not job.seed_text.strip():
        missing.append("seed_text")
    if not job.goal or not job.goal.strip():
        missing.append("goal")
    if not job.tier:
        missing.append("tier")
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Draft is incomplete, missing: {', '.join(missing)}",
        )

    # 2. Validate routing
    route = await session.execute(
        select(ModelRouting).where(ModelRouting.sim_tier == job.tier)
    )
    routing = route.scalar_one_or_none()
    if not routing:
        raise HTTPException(
            status_code=500,
            detail=f"No model routing configured for tier: {job.tier}",
        )

    # 3. Debit credits
    credits = TIER_CREDITS[job.tier]
    ledger = CreditLedger(session)
    try:
        await ledger.debit(
            user_id=user_id,
            amount=credits,
            description=f"Job creation — tier {job.tier}",
        )
    except InsufficientCreditsError:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Required: {credits}",
        )

    # 4. Set credits and generate upload URLs
    job.credits_charged = credits
    storage = _get_sim_data_storage(request)
    upload_urls = storage.generate_upload_urls(job_id=job.id)

    # 5. Dispatch to Celery
    try:
        task_result = run_simulation_task.delay(
            job_id=job.id,
            user_id=user_id,
            seed_text=job.seed_text,
            goal=job.goal,
            tier=job.tier,
            model_id=routing.model_id,
            gpu_type=routing.gpu_type,
            max_rounds=routing.max_rounds,
            vllm_args=routing.vllm_args or "",
            llm_api_key=os.getenv("LLM_API_KEY", "not-needed"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            credits_charged=credits,
            enrich_web=job.enrich_web,
            forecast_days=job.forecast_days,
            target_agents=routing.target_agents,
            upload_urls=upload_urls,
        )
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to queue simulation job")

    # 6. Transition to PENDING
    job.celery_task_id = task_result.id
    job.status = JobStatus.PENDING
    await session.commit()
    await session.refresh(job)
    return job
```

- [ ] **Step 2: Include draft router in jobs api**

In `saas/jobs/api.py`, add after the existing `router.include_router(_share_router)` line (line 20):

```python
from saas.jobs.api_draft import router as _draft_router
```

Add at line 21:
```python
router.include_router(_draft_router)
```

This mounts the draft routes under `/api/jobs/draft` (jobs prefix `/jobs` + draft prefix `/draft`).

- [ ] **Step 3: Run tests**

Run:
```bash
pytest tests/test_drafts.py -v
```

Expected: All tests PASS.

- [ ] **Step 4: Run full test suite to check for regressions**

Run:
```bash
pytest tests/ -v
```

Expected: All existing tests still pass. The nullable `goal`/`tier` change shouldn't break existing code since all non-draft jobs always have these fields set.

- [ ] **Step 5: Commit**

```bash
git add saas/jobs/api_draft.py saas/jobs/api.py
git commit -m "feat: implement draft create, update, launch endpoints (#68)"
```

---

### Task 5: Add frontend API client functions

**Files:**
- Modify: `frontend/src/api/jobs.js`

- [ ] **Step 1: Add createDraft, updateDraft, launchDraft functions**

In `frontend/src/api/jobs.js`, add after the existing `createJob` function:

```javascript
export async function createDraft(payload) {
  const body = {
    seed_text: payload.seed_text ?? '',
    enrich_web: payload.enrich_web ?? true,
    goal: payload.goal ?? null,
    tier: payload.tier ?? null,
    forecast_days: payload.forecast_days ?? null,
  }
  const response = await api.post('/jobs/draft', body)
  return response.data
}

export async function updateDraft(draftId, payload) {
  const response = await api.patch(`/jobs/draft/${draftId}`, payload)
  return response.data
}

export async function launchDraft(draftId) {
  const response = await api.post(`/jobs/draft/${draftId}/launch`)
  return response.data
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/jobs.js
git commit -m "feat: add draft API client functions (#68)"
```

---

### Task 6: Modify wizard for auto-save on step transitions

**Files:**
- Modify: `frontend/src/views/NewSimulation.vue`

- [ ] **Step 1: Add draft state and resume logic**

In `NewSimulation.vue`, add to the script setup section (after the existing state variables around line 85):

```javascript
import { useRoute } from 'vue-router'
import { createDraft, updateDraft, launchDraft, getJob } from '@/api/jobs'

const route = useRoute()
const draftId = ref(null)
const draftLoading = ref(false)
```

Add the resume-on-mount logic:

```javascript
onMounted(async () => {
  const resumeId = route.query.draft
  if (!resumeId) return

  draftLoading.value = true
  try {
    const job = await getJob(resumeId)
    if (job.status !== 'DRAFT') return

    draftId.value = job.id
    seedText.value = job.seed_text || ''
    goal.value = job.goal || ''
    selectedTier.value = job.tier || null
    enrichWeb.value = job.enrich_web ?? true
    forecastDays.value = job.forecast_days ?? null

    // Infer starting step
    if (job.goal) {
      step.value = 3
    } else if (job.seed_text) {
      step.value = 2
    } else {
      step.value = 1
    }
  } catch (err) {
    console.error('Failed to load draft:', err)
  } finally {
    draftLoading.value = false
  }
})
```

- [ ] **Step 2: Replace goToStep to auto-save on forward navigation**

Replace the existing `goToStep` function (around line 118) with:

```javascript
async function goToStep(n) {
  if (n < step.value) {
    step.value = n
    return
  }

  // Auto-save on forward step transitions
  error.value = ''
  try {
    if (step.value === 1 && n === 2) {
      // Leaving step 1: create or update draft with seed
      if (!draftId.value) {
        const draft = await createDraft({
          seed_text: seedText.value,
          enrich_web: enrichWeb.value,
        })
        draftId.value = draft.id
      } else {
        await updateDraft(draftId.value, {
          seed_text: seedText.value,
          enrich_web: enrichWeb.value,
        })
      }
    } else if (step.value === 2 && n === 3) {
      // Leaving step 2: update draft with goal
      if (draftId.value) {
        await updateDraft(draftId.value, {
          goal: goal.value,
          forecast_days: forecastDays.value,
        })
      }
    }
  } catch (err) {
    error.value = 'Failed to save draft. Please try again.'
    return
  }

  step.value = n
}
```

- [ ] **Step 3: Replace handleSubmit to launch via draft**

Replace the existing `handleSubmit` function (around line 128) with:

```javascript
async function handleSubmit() {
  await nextTick()
  loading.value = true
  error.value = ''
  try {
    if (draftId.value) {
      // Save tier, then launch draft
      await updateDraft(draftId.value, { tier: selectedTier.value })
      const job = await launchDraft(draftId.value)
      creditsStore.deduct(creditsStore.getTierCost(selectedTier.value))
      router.push(`/sim/${job.id}`)
    } else {
      // Direct launch (no draft created — user completed wizard without navigating)
      const job = await createJob({
        seed_text: seedText.value,
        goal: goal.value,
        tier: selectedTier.value,
        enrich_web: enrichWeb.value,
        forecast_days: forecastDays.value,
      })
      creditsStore.deduct(creditsStore.getTierCost(selectedTier.value))
      router.push(`/sim/${job.id}`)
    }
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to start simulation.'
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/NewSimulation.vue
git commit -m "feat: wizard auto-saves drafts on step transitions (#68)"
```

---

### Task 7: Add drafts section to dashboard

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`

- [ ] **Step 1: Add draftJobs computed property**

In `DashboardView.vue`, add after the existing `recentJobs` computed (around line 96):

```javascript
const draftJobs = computed(() =>
  jobs.value.filter(j => j.status === 'DRAFT')
)
```

Update `activeJobs` and `recentJobs` to exclude drafts:

```javascript
const activeJobs = computed(() =>
  jobs.value.filter(j => ['RUNNING', 'PROVISIONING', 'PENDING'].includes(j.status))
)

const recentJobs = computed(() =>
  jobs.value.filter(j =>
    !['RUNNING', 'PROVISIONING', 'PENDING', 'DRAFT'].includes(j.status)
  )
)
```

- [ ] **Step 2: Add drafts section to template**

In the template, add a drafts section before the active jobs section (before line 44):

```html
<!-- Drafts -->
<section v-if="draftJobs.length" class="mb-8">
  <h2 class="text-lg font-semibold text-white/90 mb-3">Drafts</h2>
  <div class="space-y-3">
    <div
      v-for="draft in draftJobs"
      :key="draft.id"
      class="group relative bg-white/5 border border-white/10 rounded-xl p-4 cursor-pointer hover:bg-white/10 transition-colors"
      @click="$router.push(`/new?draft=${draft.id}`)"
    >
      <div class="flex items-center justify-between">
        <div class="flex-1 min-w-0">
          <p class="text-white/80 truncate">
            {{ draft.goal || 'Untitled draft' }}
          </p>
          <div class="flex items-center gap-2 mt-1">
            <span class="text-xs px-2 py-0.5 rounded-full bg-white/10 text-white/50">
              Draft
            </span>
            <span v-if="draft.tier" class="text-xs text-white/40">
              {{ draft.tier }} tier
            </span>
            <span class="text-xs text-white/30">
              {{ new Date(draft.created_at).toLocaleDateString() }}
            </span>
          </div>
        </div>
        <button
          class="opacity-0 group-hover:opacity-100 text-white/30 hover:text-red-400 transition-all p-1"
          title="Delete draft"
          @click.stop="handleDelete(draft.id)"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</section>
```

The existing `handleDelete` function (line 129) already works for any job status.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/DashboardView.vue
git commit -m "feat: show draft campaigns on dashboard (#68)"
```

---

### Task 8: Run Alembic migration and final integration test

**Files:**
- Alembic migration (from Task 1)

- [ ] **Step 1: Run full backend test suite**

```bash
pytest tests/ -v
```

Expected: All tests pass including new draft tests and all existing tests.

- [ ] **Step 2: Run frontend build check**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 3: Run linter**

```bash
ruff check saas/
```

Expected: No lint errors.

- [ ] **Step 4: Final commit with all changes**

If any files were missed in previous commits:

```bash
git status
git add -A  # Only if needed
git commit -m "feat: draft campaigns — complete implementation (#68)"
```
