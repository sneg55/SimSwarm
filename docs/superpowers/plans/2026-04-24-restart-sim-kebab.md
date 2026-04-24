# Restart-sim Kebab Option Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Restart" item to the `SimCard` kebab menu that pre-fills the wizard with the source sim's settings, for sims in COMPLETED / FAILED / REFUNDED statuses.

**Architecture:** Frontend-only. `SimCard.vue` emits a new `'restart'` event. `Dashboard.vue` handles it by fetching the full source job (`getJob`) to recover `seed_text` and `forecast_days` — both absent from the dashboard's `JobSummary` — then creates a draft via the existing `POST /jobs/draft` endpoint and routes to `/sim/new?draft=<id>`. Wizard hydrates from the draft and the user launches via the existing Launch button (which is the credit-spend confirmation).

**Tech Stack:** Vue 3 (Composition API), vitest, @vue/test-utils, vue-router.

---

## File Structure

- **Modify:** `frontend/src/components/SimCard.vue` — add `'restart'` emit, a new Restart menu item above Delete, gate by status.
- **Modify:** `frontend/src/views/Dashboard.vue` — import `useRouter`, `getJob`, `createDraft`; add `handleRestart(job)`; wire `@restart` on both `<SimCard>` usages.
- **Modify:** `frontend/src/components/__tests__/SimCard.spec.js` — add tests for Restart visibility and emit.
- **Modify:** `frontend/tests/views/Dashboard.spec.js` — add mocks for `getJob` + `createDraft` and a router mock; test `handleRestart` success + failure paths.

No backend changes. No new files.

---

### Task 1: Failing tests for SimCard Restart item

**Files:**
- Test: `frontend/src/components/__tests__/SimCard.spec.js`

- [ ] **Step 1: Add three failing tests to the existing `describe('SimCard', ...)` block** (keep all existing tests; append these before the closing `})`):

```js
  it('shows Restart in kebab for terminal statuses', async () => {
    for (const status of ['COMPLETED', 'FAILED', 'REFUNDED']) {
      const wrapper = mount(SimCard, {
        props: { job: { ...baseJob, status } },
        global: { stubs: { RouterLink: RouterLinkStub } },
        attachTo: document.body,
      })
      await wrapper.findAll('button')[0].trigger('click')
      const labels = wrapper.findAll('button').map(b => b.text())
      expect(labels).toContain('Restart')
      wrapper.unmount()
    }
  })

  it('hides Restart for in-flight statuses', async () => {
    for (const status of ['RUNNING', 'PROVISIONING', 'PENDING']) {
      const wrapper = mount(SimCard, {
        props: { job: { ...baseJob, status } },
        global: { stubs: { RouterLink: RouterLinkStub } },
        attachTo: document.body,
      })
      await wrapper.findAll('button')[0].trigger('click')
      const labels = wrapper.findAll('button').map(b => b.text())
      expect(labels).not.toContain('Restart')
      wrapper.unmount()
    }
  })

  it('emits restart with the full job when Restart clicked', async () => {
    const wrapper = mount(SimCard, {
      props: { job: { ...baseJob, status: 'COMPLETED' } },
      global: { stubs: { RouterLink: RouterLinkStub } },
      attachTo: document.body,
    })
    await wrapper.findAll('button')[0].trigger('click')
    const restartBtn = wrapper.findAll('button').find(b => b.text().includes('Restart'))
    await restartBtn.trigger('click')
    expect(wrapper.emitted('restart')?.[0]?.[0]).toMatchObject({
      id: 'j1', goal: 'My Sim', status: 'COMPLETED',
    })
    wrapper.unmount()
  })
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `cd frontend && npx vitest run src/components/__tests__/SimCard.spec.js`
Expected: three new tests FAIL (the menu only contains "Delete" today, so `labels` won't contain `'Restart'`; no `'restart'` event is emitted).

- [ ] **Step 3: Commit the failing tests**

```bash
git add frontend/src/components/__tests__/SimCard.spec.js
git commit -m "test(simcard): failing tests for restart kebab item"
```

---

### Task 2: Implement Restart item in `SimCard.vue`

**Files:**
- Modify: `frontend/src/components/SimCard.vue`

- [ ] **Step 1: Add `'restart'` to `defineEmits`**

Replace line 94:

```js
const emit = defineEmits(['delete'])
```

with:

```js
const emit = defineEmits(['delete', 'restart'])
```

- [ ] **Step 2: Add a `canRestart` computed and a `handleRestart` handler**

After the existing `insightColor` computed (after line 138) and before `handleDelete` (line 140), add:

```js
const TERMINAL_STATUSES = ['COMPLETED', 'FAILED', 'REFUNDED']
const canRestart = computed(() => TERMINAL_STATUSES.includes(props.job.status))

function handleRestart() {
  menuOpen.value = false
  emit('restart', props.job)
}
```

- [ ] **Step 3: Add the Restart menu button above Delete**

In the dropdown `<div v-if="menuOpen" ...>` (currently wrapping only the Delete button at lines 75–81), insert a Restart button as the **first** child — above the Delete button, inside the same parent `<div>`:

```html
        <button
          v-if="canRestart"
          @click.prevent.stop="handleRestart"
          class="w-full text-left px-4 py-2.5 text-sm text-ocean-cyan hover:bg-ocean-teal/10 transition-colors flex items-center gap-2 border-b border-mist-depth/60"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          Restart
        </button>
```

The refresh-arrow SVG (`polyline` + curved `path`) distinguishes it from the coral trash-can for Delete. `border-b` separates the two items.

- [ ] **Step 4: Run the SimCard tests and verify they pass**

Run: `cd frontend && npx vitest run src/components/__tests__/SimCard.spec.js`
Expected: all tests (including the pre-existing Delete test and the three new Restart tests) PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SimCard.vue
git commit -m "feat(simcard): add Restart kebab item for terminal sims"
```

---

### Task 3: Failing test for `Dashboard.handleRestart`

**Files:**
- Test: `frontend/tests/views/Dashboard.spec.js`

- [ ] **Step 1: Extend the existing `vi.mock('../../src/api/jobs.js', ...)` block** (lines 4–7) to also mock `getJob` and `createDraft`:

Replace:

```js
vi.mock('../../src/api/jobs.js', () => ({
  listJobs: vi.fn(),
  deleteJob: vi.fn(),
}))
```

with:

```js
vi.mock('../../src/api/jobs.js', () => ({
  listJobs: vi.fn(),
  deleteJob: vi.fn(),
  getJob: vi.fn(),
  createDraft: vi.fn(),
}))
```

- [ ] **Step 2: Add a router mock and update the import block**

Below the existing `vi.mock` block (after the jobs.js mock, before any imports), add the router mock using `vi.hoisted` so the spy is initialized before vitest hoists the `vi.mock` call:

```js
const { routerPush } = vi.hoisted(() => ({ routerPush: vi.fn() }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: routerPush }),
}))
```

Then below the existing `import { listJobs, deleteJob } from '../../src/api/jobs.js'` (line 13), add:

```js
import { getJob, createDraft } from '../../src/api/jobs.js'
```

- [ ] **Step 3: Reset the new mocks in `beforeEach`**

In the `beforeEach` block (lines 25–30), add:

```js
    getJob.mockReset()
    createDraft.mockReset()
    routerPush.mockReset()
```

- [ ] **Step 4: Update the `SimCard` stub to expose a Restart trigger**

Replace the existing SimCard stub in the `stubs` object (line 20):

```js
  SimCard: { props: ['job'], template: '<div class="simcard">{{ job.goal }}</div>' },
```

with:

```js
  SimCard: {
    props: ['job'],
    emits: ['delete', 'restart'],
    template: `<div class="simcard">{{ job.goal }}<button class="restart-trigger" @click="$emit('restart', job)">r</button></div>`,
  },
```

- [ ] **Step 5: Append the two restart tests before the closing `})` of the `describe('Dashboard.vue', ...)` block**

```js
  it('restart fetches full job, creates draft, routes to wizard', async () => {
    listJobs.mockResolvedValue({
      jobs: [{ id: 'r1', status: 'COMPLETED', goal: 'Done' }],
      total: 1,
    })
    getBalance.mockResolvedValue({ balance: 100 })
    getJob.mockResolvedValue({
      id: 'r1',
      seed_text: 'Seed body',
      goal: 'Done',
      tier: 'small',
      enrich_web: false,
      forecast_days: 90,
    })
    createDraft.mockResolvedValue({ id: 'd42' })

    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    await wrapper.find('.restart-trigger').trigger('click')
    await flushPromises()

    expect(getJob).toHaveBeenCalledWith('r1')
    expect(createDraft).toHaveBeenCalledWith({
      seed_text: 'Seed body',
      goal: 'Done',
      tier: 'small',
      enrich_web: false,
      forecast_days: 90,
    })
    expect(routerPush).toHaveBeenCalledWith('/sim/new?draft=d42')
  })

  it('restart defaults forecast_days to 30 when source is null', async () => {
    listJobs.mockResolvedValue({
      jobs: [{ id: 'r1', status: 'COMPLETED', goal: 'Done' }],
      total: 1,
    })
    getBalance.mockResolvedValue({ balance: 100 })
    getJob.mockResolvedValue({
      id: 'r1', seed_text: 'S', goal: 'G', tier: 'small',
      enrich_web: true, forecast_days: null,
    })
    createDraft.mockResolvedValue({ id: 'd1' })

    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    await wrapper.find('.restart-trigger').trigger('click')
    await flushPromises()

    expect(createDraft).toHaveBeenCalledWith(
      expect.objectContaining({ forecast_days: 30 }),
    )
  })

  it('restart failure does not navigate and is logged', async () => {
    listJobs.mockResolvedValue({
      jobs: [{ id: 'r1', status: 'COMPLETED', goal: 'Done' }],
      total: 1,
    })
    getBalance.mockResolvedValue({ balance: 100 })
    getJob.mockRejectedValue(new Error('nope'))
    const err = vi.spyOn(console, 'error').mockImplementation(() => {})

    const wrapper = mount(Dashboard, { global: { stubs } })
    await flushPromises()
    await wrapper.find('.restart-trigger').trigger('click')
    await flushPromises()

    expect(createDraft).not.toHaveBeenCalled()
    expect(routerPush).not.toHaveBeenCalled()
    expect(err).toHaveBeenCalled()
    err.mockRestore()
  })
```

- [ ] **Step 6: Run the tests and verify the new ones fail**

Run: `cd frontend && npx vitest run tests/views/Dashboard.spec.js`
Expected: the three new tests FAIL (no `handleRestart` wired up yet). Existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/tests/views/Dashboard.spec.js
git commit -m "test(dashboard): failing tests for restart handler"
```

---

### Task 4: Implement `handleRestart` in `Dashboard.vue`

**Files:**
- Modify: `frontend/src/views/Dashboard.vue`

- [ ] **Step 1: Update imports**

At line 125, replace:

```js
import { listJobs, deleteJob } from '../api/jobs.js'
```

with:

```js
import { listJobs, deleteJob, getJob, createDraft } from '../api/jobs.js'
import { useRouter } from 'vue-router'
```

- [ ] **Step 2: Instantiate the router at the top of `<script setup>`**

After the `creditsStore` declaration at line 129 (`const creditsStore = useCreditsStore()`), add:

```js
const router = useRouter()
```

- [ ] **Step 3: Add the `handleRestart` function below `handleDelete`**

After `handleDelete` (ends at line 185), append:

```js
async function handleRestart(job) {
  try {
    const full = await getJob(job.id)
    const draft = await createDraft({
      seed_text: full.seed_text,
      goal: full.goal,
      tier: full.tier,
      enrich_web: full.enrich_web,
      forecast_days: full.forecast_days ?? 30,
    })
    router.push(`/sim/new?draft=${draft.id}`)
  } catch (err) {
    console.error('Failed to restart job:', err)
  }
}
```

- [ ] **Step 4: Wire `@restart="handleRestart"` on both `<SimCard>` usages**

At line 92 (inside the Active section), replace:

```html
<SimCard v-for="job in activeJobs" :key="job.id" :job="job" @delete="handleDelete" />
```

with:

```html
<SimCard v-for="job in activeJobs" :key="job.id" :job="job" @delete="handleDelete" @restart="handleRestart" />
```

At line 102 (inside the Recent section), replace:

```html
<SimCard v-for="job in recentJobs" :key="job.id" :job="job" @delete="handleDelete" />
```

with:

```html
<SimCard v-for="job in recentJobs" :key="job.id" :job="job" @delete="handleDelete" @restart="handleRestart" />
```

Note: the Active section gets the handler too even though in-flight sims hide Restart at the `SimCard` level — keeping the wiring uniform costs nothing and is safer than relying on the child's gate.

- [ ] **Step 5: Run the Dashboard tests and verify they pass**

Run: `cd frontend && npx vitest run tests/views/Dashboard.spec.js`
Expected: all tests PASS (existing + three new).

- [ ] **Step 6: Run the full frontend suite**

Run: `cd frontend && npm test -- --run`
Expected: all specs pass; coverage stays above the project threshold.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/Dashboard.vue
git commit -m "feat(dashboard): restart kebab pre-fills wizard with source sim settings"
```

---

### Task 5: Manual sanity check

- [ ] **Step 1: Start the dev server locally**

Run in one terminal: `cd frontend && npm run dev`
Run in another (if you need backend for `createDraft`): `uvicorn saas.main:create_app --factory --reload --port 8080`

- [ ] **Step 2: In the browser, log in and verify end-to-end**

On the dashboard:
- Open the kebab on a COMPLETED sim → see **Restart** above Delete → click.
- You should land on `/sim/new?draft=<new_id>` with seed / goal / tier / enrich toggle / forecast-days pre-filled, matching the source sim.
- Launch from the wizard, confirm the new sim appears on the dashboard.
- Open the kebab on a RUNNING sim → **Restart must not appear**.
- Open the kebab on a FAILED sim → **Restart appears** → clicking routes to the pre-filled wizard.

- [ ] **Step 3: If anything is off, fix and recommit. Otherwise proceed to push.**

```bash
git push
```

(Per the project memory note, `git push` triggers the pre-push hook that runs the full test suite; allow it time to finish. CI then deploys to Hetzner.)
