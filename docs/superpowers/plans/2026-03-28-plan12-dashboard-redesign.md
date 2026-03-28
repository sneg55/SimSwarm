# Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Dashboard as a stacked "waterline" launchpad with key insight cards, breathing status indicators, and organic empty state — matching the Deep Ocean design system.

**Architecture:** Add a `key_insight` column to the backend job model (+ migration + schema + population logic), then rebuild Dashboard.vue with a two-zone layout: waterline strip (greeting + CTA) on top, simulation cards with key insights below. Restyle CreditWarning for dark theme.

**Tech Stack:** Vue 3 (Composition API), Tailwind CSS with Deep Ocean tokens, SQLAlchemy/Alembic (backend), Pydantic schemas

**Spec reference:** Section 4 of `docs/superpowers/specs/2026-03-27-simswarm-visual-redesign.md`

---

## File Structure

```
saas/
  models/job.py                       # MODIFY - add key_insight column
  schemas/jobs.py                     # MODIFY - add key_insight to JobResponse
  workers/job_runner.py               # MODIFY - populate key_insight on completion
alembic/
  versions/d5e6f7g8h9_add_key_insight.py  # CREATE - migration
frontend/src/
  components/
    SimCard.vue                       # CREATE - simulation card with insight/status
    CreditWarning.vue                 # MODIFY - restyle for dark theme
    DashboardEmpty.vue                # CREATE - empty state with pulse rings
  views/
    Dashboard.vue                     # MODIFY - full rebuild
```

---

### Task 1: Backend — Add key_insight Column

**Files:**
- Modify: `saas/models/job.py`
- Modify: `saas/schemas/jobs.py`

- [ ] **Step 1: Add key_insight to SimulationJob model**

In `saas/models/job.py`, add this line after the `pipeline_seconds` field (line 43):

```python
    key_insight: Mapped[str | None] = mapped_column(String(200), nullable=True)
```

Also add `String` to the imports if not already there (it is — `String` is already imported on line 3).

- [ ] **Step 2: Add key_insight to JobResponse schema**

In `saas/schemas/jobs.py`, add this field to the `JobResponse` class after `error_message` (line 46):

```python
    key_insight: str | None = None
```

- [ ] **Step 3: Verify backend loads**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat/.worktrees/landing-page && python -c "from saas.models.job import SimulationJob; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add saas/models/job.py saas/schemas/jobs.py
git commit -m "feat: add key_insight field to SimulationJob model and schema"
```

---

### Task 2: Alembic Migration for key_insight

**Files:**
- Create: `alembic/versions/d5e6f7g8h9_add_key_insight.py`

- [ ] **Step 1: Create the migration file**

Create `alembic/versions/d5e6f7g8h9_add_key_insight.py`:

```python
"""add key_insight column to simulation_jobs

Revision ID: d5e6f7g8h9
Revises: c4d5e6f7g8h9
Create Date: 2026-03-28
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7g8h9"
down_revision = "c4d5e6f7g8h9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "simulation_jobs",
        sa.Column("key_insight", sa.String(200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("simulation_jobs", "key_insight")
```

- [ ] **Step 2: Commit**

```bash
git add alembic/versions/d5e6f7g8h9_add_key_insight.py
git commit -m "feat: add alembic migration for key_insight column"
```

---

### Task 3: Populate key_insight on Job Completion

**Files:**
- Modify: `saas/workers/job_runner.py`

- [ ] **Step 1: Read job_runner.py to find where results are stored**

Read `saas/workers/job_runner.py` and find the section where `result_report` is set on the job after the MiroFish pipeline completes. This is where we'll extract the first key finding.

- [ ] **Step 2: Add key_insight extraction**

After the line that sets `job.result_report = ...`, add this logic to extract a one-line insight from the report text:

```python
    # Extract key insight (first substantive sentence from report, max 200 chars)
    if job.result_report:
        lines = [l.strip() for l in job.result_report.split('\n') if l.strip()]
        # Skip markdown headings, find first content line
        insight_line = next(
            (l for l in lines if not l.startswith('#') and len(l) > 30),
            None
        )
        if insight_line:
            job.key_insight = insight_line[:200]
```

The exact insertion point depends on what `job_runner.py` looks like — place it right after `job.result_report` is assigned and before the final `session.commit()`.

- [ ] **Step 3: Run backend tests to verify nothing breaks**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat/.worktrees/landing-page && python -m pytest tests/ -x -q 2>&1 | tail -10`
Expected: Tests pass (or existing test failures unrelated to this change).

- [ ] **Step 4: Commit**

```bash
git add saas/workers/job_runner.py
git commit -m "feat: populate key_insight from report on simulation completion"
```

---

### Task 4: SimCard Component

**Files:**
- Create: `frontend/src/components/SimCard.vue`

- [ ] **Step 1: Create SimCard.vue**

Create `frontend/src/components/SimCard.vue`:

```vue
<template>
  <router-link
    :to="linkTo"
    class="block bg-gradient-to-b from-ocean-abyss to-ocean-deep border border-mist-depth rounded-xl
           px-6 py-5 relative overflow-hidden cursor-pointer group
           transition-all duration-350 ease-spring
           hover:-translate-y-0.5 hover:border-ocean-teal hover:shadow-[0_8px_32px_rgba(14,116,144,0.1)]"
  >
    <!-- Top glow line -->
    <div
      class="absolute top-0 left-0 right-0 h-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-400"
      :style="{ background: `linear-gradient(90deg, transparent, ${statusColor}, transparent)` }"
    />

    <!-- Top row: title + status -->
    <div class="flex items-center justify-between mb-2">
      <h3 class="text-base font-semibold text-mist-foam transition-colors group-hover:text-ocean-glow truncate mr-4">
        {{ job.goal || 'Simulation' }}
      </h3>
      <div class="flex items-center gap-3 flex-shrink-0">
        <span class="text-sm font-semibold text-ocean-glow opacity-0 group-hover:opacity-100 transition-opacity">
          {{ actionLabel }} &rarr;
        </span>
        <span
          class="inline-flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full border"
          :style="{
            color: statusColor,
            background: statusColor + '18',
            borderColor: statusColor + '33',
          }"
        >
          <span
            class="w-[7px] h-[7px] rounded-full"
            :class="isRunning ? 'animate-[breathe_2.5s_ease-in-out_infinite]' : ''"
            :style="{ background: statusColor }"
          />
          {{ statusLabel }}
        </span>
      </div>
    </div>

    <!-- Key insight (completed) or progress (running) or error (failed) -->
    <div v-if="job.key_insight && job.status === 'COMPLETED'" class="flex items-start gap-2.5 mb-3 px-3 py-2 bg-ocean-deep/60 rounded-lg border border-mist-depth">
      <span class="w-[3px] min-h-[18px] rounded-sm flex-shrink-0 mt-0.5" :style="{ background: insightColor }" />
      <span class="text-sm text-mist leading-snug">{{ job.key_insight }}</span>
    </div>
    <div v-else-if="job.status === 'FAILED' && job.error_message" class="text-sm text-mist-slate mb-3">
      {{ job.error_message }}
    </div>

    <!-- Meta row -->
    <div class="flex gap-4 font-mono text-xs text-mist-slate transition-colors group-hover:text-mist-drift">
      <span>{{ job.tier }} tier</span>
      <span>&middot;</span>
      <span v-if="isRunning && job.pipeline_stage">Step {{ job.pipeline_stage }}/5</span>
      <span v-else-if="job.pipeline_seconds">{{ formatDuration(job.pipeline_seconds) }}</span>
      <span v-if="isRunning && job.pipeline_stage">&middot;</span>
      <span>{{ formatTime(job.created_at) }}</span>
    </div>
  </router-link>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  job: { type: Object, required: true },
})

const STATUS_COLORS = {
  COMPLETED: '#22D3EE',
  RUNNING: '#A78BFA',
  PROVISIONING: '#A78BFA',
  PENDING: '#64748B',
  FAILED: '#FF6B6B',
  REFUNDED: '#FBBF24',
}

const STATUS_LABELS = {
  COMPLETED: 'Completed',
  RUNNING: 'Running',
  PROVISIONING: 'Provisioning',
  PENDING: 'Pending',
  FAILED: 'Failed',
  REFUNDED: 'Refunded',
}

const INSIGHT_COLORS = {
  negative: '#FF6B6B',
  positive: '#6EE7B7',
  neutral: '#FBBF24',
}

const statusColor = computed(() => STATUS_COLORS[props.job.status] || '#64748B')
const statusLabel = computed(() => STATUS_LABELS[props.job.status] || props.job.status)
const isRunning = computed(() => ['RUNNING', 'PROVISIONING'].includes(props.job.status))

const linkTo = computed(() => {
  if (props.job.status === 'COMPLETED') return `/sim/${props.job.id}/results`
  return `/sim/${props.job.id}`
})

const actionLabel = computed(() => {
  if (props.job.status === 'COMPLETED') return 'View results'
  if (isRunning.value) return 'View progress'
  if (props.job.status === 'FAILED') return 'View details'
  return 'View'
})

// Simple heuristic: if insight contains negative-sounding words, use coral
const insightColor = computed(() => {
  const text = (props.job.key_insight || '').toLowerCase()
  if (text.match(/drop|decline|negative|fell|crash|risk|crisis|fail/)) return INSIGHT_COLORS.negative
  if (text.match(/positive|grow|recovery|bull|increase|strong|rise/)) return INSIGHT_COLORS.positive
  return INSIGHT_COLORS.neutral
})

function formatDuration(seconds) {
  if (!seconds) return ''
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m ${s}s`
}

function formatTime(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const now = new Date()
  const diffMs = now - d
  const diffMin = Math.floor(diffMs / 60000)
  if (diffMin < 1) return 'Just now'
  if (diffMin < 60) return `${diffMin} min ago`
  const diffHrs = Math.floor(diffMin / 60)
  if (diffHrs < 24) return `${diffHrs} hour${diffHrs > 1 ? 's' : ''} ago`
  const diffDays = Math.floor(diffHrs / 24)
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
@keyframes breathe {
  0%, 100% { opacity: 0.4; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}
</style>
```

- [ ] **Step 2: Verify build**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat/.worktrees/landing-page/frontend && npm run build`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SimCard.vue
git commit -m "feat: add SimCard component with key insight and breathing status"
```

---

### Task 5: Dashboard Empty State

**Files:**
- Create: `frontend/src/components/DashboardEmpty.vue`

- [ ] **Step 1: Create DashboardEmpty.vue**

Create `frontend/src/components/DashboardEmpty.vue`:

```vue
<template>
  <div class="text-center py-20">
    <!-- Pulse ring illustration -->
    <div class="relative w-28 h-28 mx-auto mb-8">
      <div
        v-for="(ring, i) in rings" :key="i"
        class="absolute inset-0 rounded-full border"
        :style="{
          borderColor: ring.color,
          animation: `pulse-ring 4s ease-in-out infinite`,
          animationDelay: ring.delay,
        }"
      />
      <!-- Agent dots -->
      <div class="absolute w-2.5 h-2.5 rounded-full bg-ocean-glow opacity-60 top-2 left-1/2 -translate-x-1/2 animate-glow-breathe" />
      <div class="absolute w-2 h-2 rounded-full bg-organic-violet opacity-50 bottom-4 right-2 animate-glow-breathe" style="animation-delay: 1s;" />
      <div class="absolute w-2 h-2 rounded-full bg-coral opacity-50 bottom-4 left-2 animate-glow-breathe" style="animation-delay: 2s;" />
      <!-- Core -->
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-5 h-5 rounded-full bg-ocean-cyan/80" />
      <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-mist-foam/80" />
    </div>

    <p class="text-lg text-mist-drift max-w-sm mx-auto mb-6 leading-relaxed">
      Your ecosystem is ready.<br>What would you like to simulate today?
    </p>

    <router-link
      to="/sim/new"
      class="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-base font-semibold text-white
             bg-gradient-to-br from-ocean-cyan to-cyan-500
             glow-cyan transition-all duration-250 ease-spring
             hover:glow-cyan-lg hover:-translate-y-0.5"
    >
      Start your first simulation
    </router-link>
  </div>
</template>

<script setup>
const rings = [
  { color: 'rgba(34, 211, 238, 0.15)', delay: '0s' },
  { color: 'rgba(167, 139, 250, 0.12)', delay: '1.3s' },
  { color: 'rgba(255, 107, 107, 0.1)', delay: '2.6s' },
]
</script>

<style scoped>
@keyframes pulse-ring {
  0%, 100% { transform: scale(0.85); opacity: 0.15; }
  50% { transform: scale(1.15); opacity: 0.04; }
}
</style>
```

- [ ] **Step 2: Verify build**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat/.worktrees/landing-page/frontend && npm run build`
Expected: No errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/DashboardEmpty.vue
git commit -m "feat: add DashboardEmpty component with organic pulse ring illustration"
```

---

### Task 6: Restyle CreditWarning for Dark Theme

**Files:**
- Modify: `frontend/src/components/CreditWarning.vue`

- [ ] **Step 1: Replace CreditWarning.vue**

Replace `frontend/src/components/CreditWarning.vue`:

```vue
<template>
  <div
    v-if="creditsStore.isLow"
    class="flex items-center gap-3 px-5 py-3 rounded-xl
           bg-coral-amber/8 border border-coral-amber/20 text-coral-amber"
  >
    <svg class="w-5 h-5 flex-shrink-0 opacity-80" fill="currentColor" viewBox="0 0 20 20">
      <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
    </svg>
    <p class="text-sm">
      Low credit balance ({{ creditsStore.balance }} credits).
      <router-link to="/account" class="font-semibold underline hover:text-coral transition-colors">
        Purchase more credits
      </router-link>
      to continue running simulations.
    </p>
  </div>
</template>

<script setup>
import { useCreditsStore } from '../stores/credits.js'

const creditsStore = useCreditsStore()
</script>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/CreditWarning.vue
git commit -m "feat: restyle CreditWarning for dark ocean theme"
```

---

### Task 7: Dashboard.vue Full Rebuild

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Step 1: Replace Dashboard.vue**

Replace `frontend/src/views/Dashboard.vue`:

```vue
<template>
  <div>
    <!-- Waterline Strip -->
    <div class="relative overflow-hidden border-b border-mist-depth bg-gradient-to-b from-ocean-deep to-ocean-abyss">
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 60% 80% at 80% 50%, rgba(14,116,144,0.06), transparent)"
      />
      <div class="relative max-w-[1000px] mx-auto px-4 md:px-8 py-8 flex items-center justify-between">
        <div>
          <h1 class="text-2xl font-bold text-mist-foam tracking-tight">Welcome back</h1>
          <p class="text-sm text-mist-drift mt-1">
            <strong class="text-organic-seafoam font-semibold">{{ creditsStore.balance }} credits</strong>
            remaining
          </p>
        </div>
        <router-link
          to="/sim/new"
          class="inline-flex items-center gap-2.5 px-7 py-3.5 rounded-xl text-base font-bold text-white
                 bg-gradient-to-br from-coral to-coral-amber
                 glow-coral transition-all duration-250 ease-spring
                 hover:glow-coral-lg hover:-translate-y-0.5"
        >
          <span class="w-5 h-5 rounded-full border-2 border-white/50 flex items-center justify-center text-sm leading-none">+</span>
          New Simulation
        </router-link>
      </div>
    </div>

    <!-- Main Content -->
    <div class="max-w-[1000px] mx-auto px-4 md:px-8 py-8">

      <CreditWarning class="mb-6" />

      <!-- Loading -->
      <div v-if="loading" class="text-center py-20 text-mist-slate">Loading...</div>

      <!-- Empty State -->
      <DashboardEmpty v-else-if="jobs.length === 0" />

      <!-- Simulation List -->
      <template v-else>
        <!-- Active -->
        <template v-if="activeJobs.length > 0">
          <div class="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-mist-slate mb-4">
            Active
            <div class="flex-1 h-px bg-gradient-to-r from-mist-depth to-transparent" />
          </div>
          <div class="space-y-3 mb-10">
            <SimCard v-for="job in activeJobs" :key="job.id" :job="job" />
          </div>
        </template>

        <!-- Recent -->
        <div class="flex items-center gap-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-mist-slate mb-4">
          Recent
          <div class="flex-1 h-px bg-gradient-to-r from-mist-depth to-transparent" />
        </div>
        <div class="space-y-3">
          <SimCard v-for="job in recentJobs" :key="job.id" :job="job" />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import CreditWarning from '../components/CreditWarning.vue'
import DashboardEmpty from '../components/DashboardEmpty.vue'
import SimCard from '../components/SimCard.vue'
import { listJobs } from '../api/jobs.js'
import { getBalance } from '../api/billing.js'
import { useCreditsStore } from '../stores/credits.js'

const creditsStore = useCreditsStore()
const jobs = ref([])
const loading = ref(true)

const activeJobs = computed(() =>
  jobs.value.filter(j => ['RUNNING', 'PROVISIONING', 'PENDING'].includes(j.status))
)

const recentJobs = computed(() =>
  jobs.value.filter(j => !['RUNNING', 'PROVISIONING', 'PENDING'].includes(j.status))
)

onMounted(async () => {
  try {
    const [jobData, balanceData] = await Promise.all([listJobs(), getBalance()])
    jobs.value = jobData.jobs || jobData
    creditsStore.setBalance(balanceData.balance ?? balanceData)
  } catch (err) {
    console.error('Failed to load dashboard data:', err)
  } finally {
    loading.value = false
  }
})
</script>
```

- [ ] **Step 2: Verify build**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat/.worktrees/landing-page/frontend && npm run build`
Expected: No errors.

- [ ] **Step 3: Run frontend tests**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat/.worktrees/landing-page/frontend && npm test -- --run`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/Dashboard.vue
git commit -m "feat: rebuild Dashboard with waterline strip, SimCard list, and organic empty state"
```
