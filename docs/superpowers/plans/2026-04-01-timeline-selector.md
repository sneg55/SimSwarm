# Timeline Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a forecast timeline preset selector to Step 2 of the simulation wizard, passing `forecast_days` through the full stack to the GPU config generator.

**Architecture:** New `TimelineChips` Vue component on the goal page. `forecast_days` flows as a nullable integer through the API schema, DB model, Celery task, and GPU worker POST body. Tier gating on Step 3 dims tiers that can't handle the selected timeline. Fully backward compatible — null means "let the LLM parse it from the goal text."

**Tech Stack:** Vue 3 (Composition API), Tailwind CSS, FastAPI, SQLAlchemy, Alembic, Celery

**Spec:** `docs/superpowers/specs/2026-03-31-timeline-selector-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `frontend/src/components/wizard/TimelineChips.vue` | Pill-chip row for preset selection |
| Modify | `frontend/src/components/wizard/WizardGoal.vue` | Add TimelineChips + wire forecastDays |
| Modify | `frontend/src/components/wizard/GoalQualityMeter.vue` | Accept timelineDays prop |
| Modify | `frontend/src/components/wizard/WizardLaunch.vue` | Dim tiers by forecastDays |
| Modify | `frontend/src/views/NewSimulation.vue` | forecastDays state + pass to API |
| Modify | `frontend/src/api/jobs.js` | Send forecast_days in payload |
| Create | `frontend/src/components/__tests__/TimelineChips.spec.js` | Frontend unit tests |
| Modify | `saas/schemas/jobs.py` | Add forecast_days to JobCreate |
| Modify | `saas/models/job.py` | Add forecast_days column |
| Create | `alembic/versions/l3m4n5o6p7q8_add_forecast_days.py` | DB migration |
| Modify | `saas/api/jobs.py` | Store + pass forecast_days |
| Modify | `saas/workers/tasks.py` | Accept + forward forecast_days |
| Modify | `saas/workers/job_runner.py` | Add to JobConfig + POST /job body |
| Modify | `tests/test_jobs_api.py` | Backend test for forecast_days |

---

### Task 1: Backend — Schema + DB model + migration

**Files:**
- Modify: `saas/schemas/jobs.py`
- Modify: `saas/models/job.py`
- Create: `alembic/versions/l3m4n5o6p7q8_add_forecast_days.py`
- Modify: `tests/test_jobs_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_jobs_api.py`:

```python
async def test_create_job_with_forecast_days(client, auth_headers, funded_user, seeded_routing):
    with _mock_delay():
        response = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Breaking news: markets are volatile.",
                "goal": "Predict market sentiment",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert response.status_code == 201
    data = response.json()
    assert data["tier"] == "small"
    assert data["credits_charged"] == 30


async def test_create_job_without_forecast_days(client, auth_headers, funded_user, seeded_routing):
    """forecast_days is optional — existing behavior still works."""
    with _mock_delay():
        response = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Breaking news: markets are volatile.",
                "goal": "Predict market sentiment",
                "tier": "small",
            },
        )
    assert response.status_code == 201
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_jobs_api.py::test_create_job_with_forecast_days -v`
Expected: FAIL — 422 because `forecast_days` is not a recognized field in `JobCreate`

- [ ] **Step 3: Add forecast_days to schema**

In `saas/schemas/jobs.py`, add to `JobCreate`:

```python
class JobCreate(BaseModel):
    seed_text: str
    goal: str
    tier: TierEnum
    enrich_web: bool = True
    forecast_days: int | None = None
```

- [ ] **Step 4: Add forecast_days to DB model**

In `saas/models/job.py`, add column to `SimulationJob`:

```python
forecast_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 5: Create Alembic migration**

Create `alembic/versions/l3m4n5o6p7q8_add_forecast_days.py`:

```python
"""add forecast_days column to simulation_jobs

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "l3m4n5o6p7q8"
down_revision = "k2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_jobs", sa.Column("forecast_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_jobs", "forecast_days")
```

- [ ] **Step 6: Store forecast_days in API**

In `saas/api/jobs.py`, add `forecast_days` to the job row creation (~line 65):

```python
    job = SimulationJob(
        user_id=user_id,
        seed_text=body.seed_text,
        goal=body.goal,
        tier=body.tier.value,
        credits_charged=credits,
        status=JobStatus.PENDING,
        enrich_web=body.enrich_web,
        forecast_days=body.forecast_days,
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_jobs_api.py -v`
Expected: ALL PASS (both new tests + all existing tests)

- [ ] **Step 8: Verify single alembic head**

Run: `alembic heads`
Expected: Single head `l3m4n5o6p7q8`

- [ ] **Step 9: Commit**

```bash
git add saas/schemas/jobs.py saas/models/job.py saas/api/jobs.py alembic/versions/l3m4n5o6p7q8_add_forecast_days.py tests/test_jobs_api.py
git commit -m "feat: add forecast_days field to job schema, model, and API"
```

---

### Task 2: Backend — Pass forecast_days through Celery to GPU worker

**Files:**
- Modify: `saas/api/jobs.py`
- Modify: `saas/workers/tasks.py`
- Modify: `saas/workers/job_runner.py`

- [ ] **Step 1: Add forecast_days to Celery task dispatch**

In `saas/api/jobs.py`, add `forecast_days` to the `run_simulation_task.delay()` call (~line 79):

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
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            credits_charged=credits,
            enrich_web=body.enrich_web,
            forecast_days=body.forecast_days,
        )
```

- [ ] **Step 2: Accept forecast_days in Celery task**

In `saas/workers/tasks.py`, add `forecast_days` parameter to `run_simulation_task` (~line 49):

```python
def run_simulation_task(
    self,
    job_id: int,
    user_id: str,
    seed_text: str,
    goal: str,
    tier: str,
    model_id: str,
    gpu_type: str,
    max_rounds: int,
    vllm_args: str,
    llm_api_key: str,
    openai_api_key: str = "",
    credits_charged: int = 0,
    enrich_web: bool = True,
    forecast_days: int | None = None,
) -> dict:
```

And pass it to JobConfig (~line 73):

```python
    config = JobConfig(
        job_id=job_id,
        user_id=user_id,
        seed_text=enriched_seed_text,
        goal=goal,
        tier=tier,
        model_id=model_id,
        gpu_type=gpu_type,
        max_rounds=max_rounds,
        vllm_args=vllm_args,
        llm_api_key=llm_api_key,
        openai_api_key=openai_api_key,
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        forecast_days=forecast_days,
    )
```

- [ ] **Step 3: Add forecast_days to JobConfig dataclass**

In `saas/workers/job_runner.py`, add field to `JobConfig` (~line 47):

```python
@dataclass
class JobConfig:
    job_id: int
    user_id: str
    seed_text: str
    goal: str
    tier: str
    model_id: str
    gpu_type: str
    max_rounds: int
    vllm_args: str
    llm_api_key: str
    openai_api_key: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    forecast_days: int | None = None
```

- [ ] **Step 4: Include forecast_days in GPU worker POST body**

In `saas/workers/job_runner.py`, update the `_execute_pipeline` method's POST /job payload (~line 259):

```python
            resp = await client.post(f"{worker_url}/job", json={
                "seed_text": config.seed_text,
                "goal": config.goal,
                "max_rounds": config.max_rounds,
                "forecast_days": config.forecast_days,
            }, timeout=30)
```

- [ ] **Step 5: Run backend tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add saas/api/jobs.py saas/workers/tasks.py saas/workers/job_runner.py
git commit -m "feat: pass forecast_days through Celery task to GPU worker"
```

---

### Task 3: Frontend — TimelineChips component

**Files:**
- Create: `frontend/src/components/wizard/TimelineChips.vue`
- Create: `frontend/src/components/__tests__/TimelineChips.spec.js`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/__tests__/TimelineChips.spec.js`:

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import TimelineChips from '../wizard/TimelineChips.vue'

describe('TimelineChips', () => {
  it('renders all 6 preset chips', () => {
    const wrapper = mount(TimelineChips)
    const buttons = wrapper.findAll('button')
    expect(buttons.length).toBe(6)
    expect(buttons[0].text()).toBe('1 day')
    expect(buttons[5].text()).toBe('1 year')
  })

  it('emits update:modelValue when a chip is clicked', async () => {
    const wrapper = mount(TimelineChips)
    await wrapper.findAll('button')[2].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([30])
  })

  it('highlights the selected chip', () => {
    const wrapper = mount(TimelineChips, { props: { modelValue: 7 } })
    const buttons = wrapper.findAll('button')
    expect(buttons[1].classes()).toContain('border-ocean-cyan')
  })

  it('deselects when clicking the active chip', async () => {
    const wrapper = mount(TimelineChips, { props: { modelValue: 30 } })
    await wrapper.findAll('button')[2].trigger('click')
    expect(wrapper.emitted('update:modelValue')[0]).toEqual([null])
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/components/__tests__/TimelineChips.spec.js`
Expected: FAIL — module not found

- [ ] **Step 3: Create TimelineChips.vue**

Create `frontend/src/components/wizard/TimelineChips.vue`:

```vue
<template>
  <div class="mt-4">
    <div class="text-xs font-semibold uppercase tracking-wider text-mist-slate mb-2">Forecast timeline</div>
    <div class="flex flex-wrap gap-2">
      <button
        v-for="preset in presets"
        :key="preset.days"
        @click="toggle(preset.days)"
        class="px-3.5 py-1.5 rounded-full text-sm font-medium border transition-all duration-200"
        :class="modelValue === preset.days
          ? 'border-ocean-cyan bg-ocean-cyan/10 text-ocean-cyan'
          : 'border-mist-depth bg-ocean-deep text-mist-drift hover:border-mist-slate hover:text-mist-foam'"
      >
        {{ preset.label }}
      </button>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Number, default: null },
})

const emit = defineEmits(['update:modelValue'])

const presets = [
  { label: '1 day', days: 1 },
  { label: '1 week', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: '6 months', days: 180 },
  { label: '1 year', days: 365 },
]

function toggle(days) {
  emit('update:modelValue', props.modelValue === days ? null : days)
}
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/components/__tests__/TimelineChips.spec.js`
Expected: ALL 4 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/wizard/TimelineChips.vue frontend/src/components/__tests__/TimelineChips.spec.js
git commit -m "feat: add TimelineChips component with presets and tests"
```

---

### Task 4: Frontend — Wire TimelineChips into wizard flow

**Files:**
- Modify: `frontend/src/components/wizard/WizardGoal.vue`
- Modify: `frontend/src/components/wizard/GoalQualityMeter.vue`
- Modify: `frontend/src/views/NewSimulation.vue`
- Modify: `frontend/src/api/jobs.js`

- [ ] **Step 1: Add forecastDays to WizardGoal**

Replace `frontend/src/components/wizard/WizardGoal.vue`:

```vue
<template>
  <div>
    <div class="mb-5">
      <div class="font-mono text-xs text-ocean-cyan tracking-wide mb-2">Step 2 of 3</div>
      <h2 class="text-3xl font-extrabold text-mist-foam tracking-tight leading-tight">What do you want to know?</h2>
      <p class="text-[15px] text-mist-drift mt-2">Describe your research question. The swarm will simulate how stakeholders, markets, and media react.</p>
    </div>

    <textarea
      :value="goal"
      @input="$emit('update:goal', $event.target.value)"
      placeholder="e.g. How will retail investors and analysts react to our Q1 earnings miss over the next 30 days? What sentiment shifts and price narratives should we expect?"
      class="w-full bg-ocean-abyss border border-mist-depth rounded-2xl p-5 text-base text-mist resize-none min-h-[140px] outline-none leading-relaxed transition-all focus:border-ocean-cyan focus:shadow-[0_0_0_3px_rgba(14,116,144,0.15)]"
    />

    <TimelineChips :modelValue="forecastDays" @update:modelValue="$emit('update:forecastDays', $event)" />

    <GoalQualityMeter :goal="goal" :timelineDays="forecastDays" />

    <div class="mt-6">
      <GoalTemplateCards :seed-text="seedText" @select="onTemplateSelect" />
    </div>
  </div>
</template>

<script setup>
import GoalQualityMeter from './GoalQualityMeter.vue'
import GoalTemplateCards from './GoalTemplateCards.vue'
import TimelineChips from './TimelineChips.vue'

const props = defineProps({
  goal: { type: String, default: '' },
  seedText: { type: String, default: '' },
  forecastDays: { type: Number, default: null },
})

const emit = defineEmits(['update:goal', 'update:forecastDays'])

function onTemplateSelect(text) {
  emit('update:goal', text)
}
</script>
```

- [ ] **Step 2: Update GoalQualityMeter to accept timelineDays**

In `frontend/src/components/wizard/GoalQualityMeter.vue`, add the prop and use it in scoring:

Add to props:

```javascript
const props = defineProps({
  goal: { type: String, default: '' },
  timelineDays: { type: Number, default: null },
})
```

In `score` computed, change the timeframe line:

```javascript
  if (TIMEFRAME_RE.test(g) || props.timelineDays) s++
```

In `activeTips` computed, change the timeframe tip:

```javascript
  if (!TIMEFRAME_RE.test(g) && !props.timelineDays) tips.push("Tip: Add a timeframe (e.g. 'over 30 days' or 'within the next quarter')")
```

- [ ] **Step 3: Add forecastDays state to NewSimulation.vue**

In `frontend/src/views/NewSimulation.vue`:

Add ref (~line 80):

```javascript
const forecastDays = ref(null)
```

Update WizardGoal usage (~line 30):

```html
      <WizardGoal v-model:goal="goal" v-model:forecastDays="forecastDays" :seed-text="seedText" />
```

Update WizardLaunch usage (~line 41):

```html
      <WizardLaunch v-model:tier="selectedTier" :forecastDays="forecastDays" />
```

Update `handleSubmit` to pass forecastDays (~line 131):

```javascript
    const job = await createJob({
      seed_text: seedText.value,
      goal: goal.value,
      tier: selectedTier.value,
      enrich_web: enrichWeb.value,
      forecast_days: forecastDays.value,
    })
```

- [ ] **Step 4: Update jobs.js API client**

In `frontend/src/api/jobs.js`, add `forecast_days` to the payload:

```javascript
export async function createJob(payload) {
  const body = {
    seed_text: payload.seed_text,
    goal: payload.goal,
    tier: payload.tier,
    enrich_web: payload.enrich_web ?? true,
    forecast_days: payload.forecast_days ?? null,
  }
  const response = await api.post('/jobs', body)
  return response.data
}
```

- [ ] **Step 5: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS

- [ ] **Step 6: Build check**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/wizard/WizardGoal.vue frontend/src/components/wizard/GoalQualityMeter.vue frontend/src/views/NewSimulation.vue frontend/src/api/jobs.js
git commit -m "feat: wire TimelineChips into wizard flow and API"
```

---

### Task 5: Frontend — Tier gating on Step 3

**Files:**
- Modify: `frontend/src/components/wizard/WizardLaunch.vue`

- [ ] **Step 1: Add forecastDays prop and tier gating logic**

In `frontend/src/components/wizard/WizardLaunch.vue`, add the prop and gating:

Add to props:

```javascript
const props = defineProps({
  forecastDays: { type: Number, default: null },
})
```

Add tier max days mapping:

```javascript
const TIER_MAX_DAYS = { small: 30, medium: 180, large: 365 }

function tierFitsTimeline(tierId) {
  if (!props.forecastDays) return true
  return props.forecastDays <= TIER_MAX_DAYS[tierId]
}
```

Update the tier button's `:disabled` and `:class`:

```html
        :disabled="!creditsStore.canAfford(tier.id) || !tierFitsTimeline(tier.id)"
```

Add a hint below each tier card when it doesn't fit. Inside the `<button>` for each tier, at the bottom:

```html
        <div v-if="!tierFitsTimeline(tier.id)" class="text-[10px] text-coral/70 mt-1">
          Needs {{ tier.id === 'small' ? 'Medium' : 'Large' }}+
        </div>
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 3: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/wizard/WizardLaunch.vue
git commit -m "feat: dim tier cards that can't handle selected forecast timeline"
```

---

### Task 6: Run full test suite + final build

**Files:** None (verification only)

- [ ] **Step 1: Run backend tests**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: ALL PASS

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Verify alembic single head**

Run: `alembic heads`
Expected: Single head `l3m4n5o6p7q8`

- [ ] **Step 5: Commit toolbar fix from earlier (if not yet committed)**

The ResultsToolbar truncation fix should be included:

```bash
git add frontend/src/components/results/ResultsToolbar.vue
git commit -m "fix: truncate long goal text in results toolbar"
```
