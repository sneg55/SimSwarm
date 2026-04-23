# Story Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Map simulation rounds onto the user-selected forecast horizon and surface moments (market inflections, coalition shifts, viral posts, findings) on a horizontal band + upgraded vertical rail on the Simulation Results story view.

**Architecture:** Pure-function composable transforms existing `structured` signals + MinIO sim-data (`market_curves.json`, `top_posts.json`, `agent_trajectories.json`) into `{ roundDates[], moments[] }`. Two Vue components render projections of the same data — horizontal band (`StoryTimelineBand.vue`, new, after hero) and vertical rail (`StoryTimeline.vue`, upgraded). A shared scroll-sync composable drives both. Backend surfaces `forecast_days` on the job response so the client can compute date mapping.

**Tech Stack:** Vue 3 Composition API, Vitest, Tailwind CSS (existing palette tokens), FastAPI + Pydantic v2 (one-field addition to `JobResponse`).

**Spec:** `docs/superpowers/specs/2026-04-23-story-timeline-design.md`

---

## File Structure

**New files:**
- `frontend/src/composables/useSimTimeline.js` — pure function: inputs → `{ start, end, roundDates, moments }`
- `frontend/src/composables/useStoryScrollSync.js` — shared scroll-listener + active-round state
- `frontend/src/components/results/StoryTimelineBand.vue` — horizontal date band
- `frontend/src/composables/__tests__/useSimTimeline.spec.js`
- `frontend/src/composables/__tests__/useStoryScrollSync.spec.js`
- `frontend/src/components/results/__tests__/StoryTimelineBand.spec.js`

**Modified files:**
- `saas/jobs/schemas.py` — add `forecast_days` to `JobResponse`
- `tests/test_jobs_api.py` (or nearest equivalent) — assert the field appears
- `frontend/src/components/results/StoryTimeline.vue` — accept optional `moments` prop, render secondary dots
- `frontend/src/components/results/__tests__` — add/extend `StoryTimeline.spec.js`
- `frontend/src/views/SimulationResults.vue` — load sim-data for story view, build timeline, pass to components

---

## Task 1: Expose `forecast_days` on `JobResponse`

**Files:**
- Modify: `saas/jobs/schemas.py:57-80`
- Test: `tests/jobs/test_job_api.py` (verify name with `ls tests/jobs/`; create if none exists)

- [ ] **Step 1: Locate the existing job-response test file**

Run:
```bash
ls tests/jobs/ 2>/dev/null || ls tests/ | grep -i job
```

If `tests/jobs/test_job_api.py` exists, use it. Otherwise pick the nearest test touching `JobResponse` (search `grep -rn "JobResponse\|result_structured" tests/`). If no fixture exists that returns a completed job, extend `funded_user` or create a small fixture `completed_job` that inserts a `SimulationJob` with `forecast_days=30` and `status="completed"`.

- [ ] **Step 2: Write the failing test**

Add to the chosen test file:

```python
async def test_job_response_includes_forecast_days(
    client, auth_headers, db_session
):
    from saas.jobs.models import SimulationJob
    job = SimulationJob(
        user_id="test-user",
        seed_text="seed",
        goal="goal",
        tier="small",
        credits_charged=10,
        status="completed",
        forecast_days=90,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    resp = await client.get(f"/jobs/{job.id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["forecast_days"] == 90
```

Adjust `user_id` / `auth_headers` to whatever the existing fixtures supply. If `auth_headers` encodes a specific user, set `job.user_id` to match.

- [ ] **Step 3: Run the test to verify it fails**

Run: `pytest tests/jobs/test_job_api.py::test_job_response_includes_forecast_days -v`
Expected: FAIL — `KeyError: 'forecast_days'` or `AssertionError` because the field is not in the serialized response.

- [ ] **Step 4: Add the field to `JobResponse`**

Edit `saas/jobs/schemas.py` — in the `JobResponse` class (around line 57), add after `enrich_web: bool = True`:

```python
    forecast_days: int | None = None
```

Place it next to other job-config fields, keeping alphabetical or grouped order consistent with the existing class.

- [ ] **Step 5: Run the test to verify it passes**

Run: `pytest tests/jobs/test_job_api.py::test_job_response_includes_forecast_days -v`
Expected: PASS.

- [ ] **Step 6: Run the full job-api test file to check no regressions**

Run: `pytest tests/jobs/ -v`
Expected: all previously-passing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add saas/jobs/schemas.py tests/jobs/test_job_api.py
git commit -m "feat(api): expose forecast_days on JobResponse

Needed by the story-timeline feature to map rounds onto the user's
forecast horizon client-side."
```

---

## Task 2: `useSimTimeline` composable — skeleton + date mapping

**Files:**
- Create: `frontend/src/composables/useSimTimeline.js`
- Test: `frontend/src/composables/__tests__/useSimTimeline.spec.js`

- [ ] **Step 1: Write the failing test for date mapping**

Create `frontend/src/composables/__tests__/useSimTimeline.spec.js`:

```js
import { describe, it, expect } from 'vitest'
import { useSimTimeline } from '../useSimTimeline'

const START = '2026-01-01T00:00:00Z'

describe('useSimTimeline — date mapping', () => {
  it('spaces rounds evenly across the horizon', () => {
    const t = useSimTimeline({
      startedAt: START,
      forecastDays: 30,
      roundCount: 4,
      structured: {},
      marketCurves: [],
      topPosts: [],
      agentTrajectories: [],
    })
    expect(t.roundDates).toHaveLength(4)
    expect(t.roundDates[0].toISOString()).toBe('2026-01-01T00:00:00.000Z')
    expect(t.roundDates[3].toISOString()).toBe('2026-01-31T00:00:00.000Z')
    const deltaMs = t.roundDates[1] - t.roundDates[0]
    expect(deltaMs).toBe((30 * 86400 * 1000) / 3)
  })

  it('handles a single-round sim by pinning to the start', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 30, roundCount: 1,
      structured: {}, marketCurves: [], topPosts: [], agentTrajectories: [],
    })
    expect(t.roundDates).toHaveLength(1)
    expect(t.roundDates[0].toISOString()).toBe('2026-01-01T00:00:00.000Z')
  })

  it('returns an empty timeline when inputs are missing', () => {
    const t = useSimTimeline({
      startedAt: null, forecastDays: null, roundCount: 0,
      structured: null, marketCurves: null, topPosts: null, agentTrajectories: null,
    })
    expect(t.roundDates).toEqual([])
    expect(t.moments).toEqual([])
    expect(t.start).toBeNull()
    expect(t.end).toBeNull()
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Write the minimal implementation**

Create `frontend/src/composables/useSimTimeline.js`:

```js
/**
 * Pure function: maps simulation rounds to calendar dates over the user-
 * selected forecast horizon, and extracts moments to pin on the timeline.
 *
 * Returns: { start: Date|null, end: Date|null, roundDates: Date[], moments: [] }
 */
export function useSimTimeline({
  startedAt,
  forecastDays,
  roundCount,
  structured,
  marketCurves,
  topPosts,
  agentTrajectories,
}) {
  const empty = { start: null, end: null, roundDates: [], moments: [] }
  if (!startedAt || !forecastDays || !roundCount || roundCount < 1) return empty

  const start = new Date(startedAt)
  if (Number.isNaN(start.getTime())) return empty
  const horizonMs = forecastDays * 86400 * 1000
  const end = new Date(start.getTime() + horizonMs)

  const roundDates = []
  if (roundCount === 1) {
    roundDates.push(start)
  } else {
    const step = horizonMs / (roundCount - 1)
    for (let i = 0; i < roundCount; i++) {
      roundDates.push(new Date(start.getTime() + i * step))
    }
  }

  const moments = []
  return { start, end, roundDates, moments }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: PASS (3/3).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSimTimeline.js frontend/src/composables/__tests__/useSimTimeline.spec.js
git commit -m "feat(timeline): add useSimTimeline date-mapping skeleton

Maps round index to real calendar dates over the forecast horizon.
Moment extraction added in follow-up commits."
```

---

## Task 3: `useSimTimeline` — market inflection moments

**Files:**
- Modify: `frontend/src/composables/useSimTimeline.js`
- Modify: `frontend/src/composables/__tests__/useSimTimeline.spec.js`

`marketCurves` shape (from `market_curves.json` produced by the extractor) is an array of markets, each `{ market_id, question, points: [{ round_num, price_yes, price_no }, ...] }`.

- [ ] **Step 1: Add failing test for market inflections**

Append to the spec:

```js
describe('useSimTimeline — market moments', () => {
  it('emits a moment when |Δprice_yes| >= 15pp between consecutive rounds', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 5,
      structured: {},
      marketCurves: [{
        market_id: 'm1',
        question: 'Will X happen?',
        points: [
          { round_num: 1, price_yes: 0.50 },
          { round_num: 2, price_yes: 0.52 },  // +2pp, ignored
          { round_num: 3, price_yes: 0.70 },  // +18pp, keep
          { round_num: 4, price_yes: 0.55 },  // -15pp, keep (boundary)
          { round_num: 5, price_yes: 0.60 },  // +5pp, ignored
        ],
      }],
      topPosts: [], agentTrajectories: [],
    })
    const market = t.moments.filter(m => m.type === 'market')
    expect(market).toHaveLength(2)
    expect(market[0].roundIndex).toBe(2)  // 0-indexed round 3
    expect(market[0].refId).toBe('m1')
    expect(market[0].title).toContain('Will X happen?')
    expect(market[1].roundIndex).toBe(3)
  })

  it('skips markets with fewer than 2 points', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 3,
      structured: {},
      marketCurves: [{ market_id: 'm1', question: 'Q', points: [{ round_num: 1, price_yes: 0.5 }] }],
      topPosts: [], agentTrajectories: [],
    })
    expect(t.moments.filter(m => m.type === 'market')).toHaveLength(0)
  })
})
```

- [ ] **Step 2: Run tests — verify new ones fail**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: new tests FAIL, prior ones still pass.

- [ ] **Step 3: Implement market-moment extraction**

In `useSimTimeline.js`, before `return { start, end, roundDates, moments }`, add:

```js
  const THRESHOLD = 0.15
  for (const market of marketCurves || []) {
    const pts = Array.isArray(market?.points) ? market.points : []
    if (pts.length < 2) continue
    for (let i = 1; i < pts.length; i++) {
      const delta = pts[i].price_yes - pts[i - 1].price_yes
      if (Math.abs(delta) >= THRESHOLD) {
        const round = pts[i].round_num
        const roundIndex = Math.max(0, Math.min(roundCount - 1, round - 1))
        moments.push({
          id: `market:${market.market_id}:${round}`,
          type: 'market',
          roundIndex,
          date: roundDates[roundIndex],
          title: market.question || market.market_id,
          detail: `${delta >= 0 ? '+' : ''}${Math.round(delta * 100)}pp YES`,
          refId: market.market_id,
        })
      }
    }
  }
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSimTimeline.js frontend/src/composables/__tests__/useSimTimeline.spec.js
git commit -m "feat(timeline): extract market-inflection moments"
```

---

## Task 4: `useSimTimeline` — finding moments

**Files:**
- Modify: `frontend/src/composables/useSimTimeline.js`
- Modify: `frontend/src/composables/__tests__/useSimTimeline.spec.js`

Findings live in `structured.findings` — each is a free-form object. They don't carry a `round_num`. Anchor strategy: if the finding's slot matches a phase boundary (`structured.phase_boundaries`), pin to the phase's end-round. Otherwise pin to the midpoint round.

Phase shape (from `simswarm/story_signals.py:156`): `{ phase: 'Early'|'Mid'|'Late'|'Full horizon', rounds: [start, end], week_range, dominant_topic }`.

- [ ] **Step 1: Failing test for findings**

Append:

```js
describe('useSimTimeline — finding moments', () => {
  it('anchors findings to phase end-rounds when phase matches', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 30, roundCount: 9,
      structured: {
        findings: [
          { title: 'F1', phase: 'Early' },
          { title: 'F2', phase: 'Late' },
          { title: 'F3' },
        ],
        phase_boundaries: [
          { phase: 'Early', rounds: [1, 3] },
          { phase: 'Mid', rounds: [4, 6] },
          { phase: 'Late', rounds: [7, 9] },
        ],
      },
      marketCurves: [], topPosts: [], agentTrajectories: [],
    })
    const f = t.moments.filter(m => m.type === 'finding')
    expect(f).toHaveLength(3)
    expect(f[0].title).toBe('F1'); expect(f[0].roundIndex).toBe(2)  // round 3
    expect(f[1].title).toBe('F2'); expect(f[1].roundIndex).toBe(8)  // round 9
    expect(f[2].title).toBe('F3'); expect(f[2].roundIndex).toBe(4)  // midpoint
  })

  it('returns no finding moments when findings array is missing', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 5,
      structured: {}, marketCurves: [], topPosts: [], agentTrajectories: [],
    })
    expect(t.moments.filter(m => m.type === 'finding')).toEqual([])
  })
})
```

- [ ] **Step 2: Run tests — verify new ones fail**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: new tests FAIL.

- [ ] **Step 3: Implement finding extraction**

Add before `return` in `useSimTimeline.js`:

```js
  const findings = Array.isArray(structured?.findings) ? structured.findings : []
  const phases = Array.isArray(structured?.phase_boundaries) ? structured.phase_boundaries : []
  const midRound = Math.max(1, Math.ceil(roundCount / 2))
  findings.forEach((f, idx) => {
    const phase = phases.find(p => p.phase === f.phase)
    const round = phase ? phase.rounds[1] : midRound
    const roundIndex = Math.max(0, Math.min(roundCount - 1, round - 1))
    moments.push({
      id: `finding:${idx}`,
      type: 'finding',
      roundIndex,
      date: roundDates[roundIndex],
      title: f.title || f.headline || `Finding ${idx + 1}`,
      detail: f.summary || f.description || '',
      refId: `story-finding-${idx}`,
    })
  })
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSimTimeline.js frontend/src/composables/__tests__/useSimTimeline.spec.js
git commit -m "feat(timeline): anchor findings to phase end-rounds"
```

---

## Task 5: `useSimTimeline` — viral post moments

**Files:**
- Modify: `frontend/src/composables/useSimTimeline.js`
- Modify: `frontend/src/composables/__tests__/useSimTimeline.spec.js`

`topPosts` comes from `top_posts.json`. Shape (observed from extractor): array of `{ round_num, agent_name, text, engagement, platform }`. Strategy: for each round, keep the single post with the highest `engagement`, subject to a minimum floor of 1 (i.e., ignore rounds where nobody engaged).

- [ ] **Step 1: Failing test**

Append:

```js
describe('useSimTimeline — post moments', () => {
  it('keeps top-engagement post per round, above floor', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 3,
      structured: {},
      marketCurves: [],
      topPosts: [
        { round_num: 1, agent_name: 'A', text: 'low',  engagement: 0 },  // below floor
        { round_num: 2, agent_name: 'B', text: 'mid',  engagement: 3 },
        { round_num: 2, agent_name: 'C', text: 'high', engagement: 7 },  // winner R2
        { round_num: 3, agent_name: 'D', text: 'only', engagement: 2 },  // winner R3
      ],
      agentTrajectories: [],
    })
    const posts = t.moments.filter(m => m.type === 'post')
    expect(posts).toHaveLength(2)
    expect(posts[0].roundIndex).toBe(1); expect(posts[0].title).toContain('C')
    expect(posts[1].roundIndex).toBe(2); expect(posts[1].title).toContain('D')
  })
})
```

- [ ] **Step 2: Run tests — verify new one fails**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: new test FAILS.

- [ ] **Step 3: Implement post extraction**

Add:

```js
  const postsByRound = new Map()
  for (const p of topPosts || []) {
    const eng = Number(p.engagement) || 0
    if (eng < 1) continue
    const prev = postsByRound.get(p.round_num)
    if (!prev || eng > prev.engagement) postsByRound.set(p.round_num, p)
  }
  for (const [round, p] of postsByRound) {
    const roundIndex = Math.max(0, Math.min(roundCount - 1, round - 1))
    moments.push({
      id: `post:${round}:${p.agent_name}`,
      type: 'post',
      roundIndex,
      date: roundDates[roundIndex],
      title: `${p.agent_name}`,
      detail: (p.text || '').slice(0, 120),
      refId: null,
    })
  }
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSimTimeline.js frontend/src/composables/__tests__/useSimTimeline.spec.js
git commit -m "feat(timeline): extract top-engagement post per round"
```

---

## Task 6: `useSimTimeline` — coalition-shift moments

**Files:**
- Modify: `frontend/src/composables/useSimTimeline.js`
- Modify: `frontend/src/composables/__tests__/useSimTimeline.spec.js`

`agentTrajectories` is from `agent_trajectories.json`, shape: `[{ agent_name, stance_per_round: [{ round_num, stance }] }]`. Strategy for v1: bucket agents by stance at each round, compute stance distribution per round; emit a moment when the plurality-stance changes round-over-round. Keep simple; differentiate on *that* rather than stakeholder-group formation (deferred).

- [ ] **Step 1: Failing test**

Append:

```js
describe('useSimTimeline — coalition moments', () => {
  it('emits a moment when plurality stance flips round-over-round', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 4,
      structured: {}, marketCurves: [], topPosts: [],
      agentTrajectories: [
        { agent_name: 'a', stance_per_round: [
          { round_num: 1, stance: 'pro' }, { round_num: 2, stance: 'pro' },
          { round_num: 3, stance: 'con' }, { round_num: 4, stance: 'con' },
        ]},
        { agent_name: 'b', stance_per_round: [
          { round_num: 1, stance: 'pro' }, { round_num: 2, stance: 'pro' },
          { round_num: 3, stance: 'con' }, { round_num: 4, stance: 'pro' },
        ]},
      ],
    })
    const shifts = t.moments.filter(m => m.type === 'coalition')
    // R1→R2: pro→pro, no shift. R2→R3: pro→con, shift. R3→R4: con→pro (plurality tie → pick con->pro as shift).
    expect(shifts.map(s => s.roundIndex)).toEqual([2, 3])
    expect(shifts[0].detail).toContain('pro')
    expect(shifts[0].detail).toContain('con')
  })

  it('ignores neutral/unknown stances when computing plurality', () => {
    const t = useSimTimeline({
      startedAt: START, forecastDays: 10, roundCount: 2,
      structured: {}, marketCurves: [], topPosts: [],
      agentTrajectories: [
        { agent_name: 'a', stance_per_round: [
          { round_num: 1, stance: 'neutral' }, { round_num: 2, stance: 'neutral' },
        ]},
      ],
    })
    expect(t.moments.filter(m => m.type === 'coalition')).toEqual([])
  })
})
```

- [ ] **Step 2: Run tests — verify new ones fail**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: FAIL.

- [ ] **Step 3: Implement coalition extraction**

Add helper at top of file (below the `useSimTimeline` function export) or inline:

```js
  function pluralityStance(round, trajectories) {
    const counts = {}
    for (const a of trajectories) {
      const entry = (a.stance_per_round || []).find(e => e.round_num === round)
      const s = entry?.stance
      if (!s || s === 'neutral' || s === 'unknown') continue
      counts[s] = (counts[s] || 0) + 1
    }
    let best = null, bestCount = 0
    for (const [s, c] of Object.entries(counts)) {
      if (c > bestCount) { best = s; bestCount = c }
    }
    return best
  }
```

Inside `useSimTimeline`, after `roundDates` is built and before post extraction:

```js
  const trajectories = Array.isArray(agentTrajectories) ? agentTrajectories : []
  if (trajectories.length && roundCount >= 2) {
    let prev = pluralityStance(1, trajectories)
    for (let r = 2; r <= roundCount; r++) {
      const curr = pluralityStance(r, trajectories)
      if (prev && curr && prev !== curr) {
        const roundIndex = r - 1
        moments.push({
          id: `coalition:${r}`,
          type: 'coalition',
          roundIndex,
          date: roundDates[roundIndex],
          title: `Majority flips ${prev} → ${curr}`,
          detail: `Round ${r}: plurality shifted from ${prev} to ${curr}`,
          refId: null,
        })
      }
      if (curr) prev = curr
    }
  }
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: all PASS.

- [ ] **Step 5: Sort moments by roundIndex before returning**

Replace `return { start, end, roundDates, moments }` with:

```js
  moments.sort((a, b) => a.roundIndex - b.roundIndex)
  return { start, end, roundDates, moments }
```

Re-run tests: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js` — all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/composables/useSimTimeline.js frontend/src/composables/__tests__/useSimTimeline.spec.js
git commit -m "feat(timeline): detect plurality-stance coalition shifts"
```

---

## Task 7: `useStoryScrollSync` composable

**Files:**
- Create: `frontend/src/composables/useStoryScrollSync.js`
- Test: `frontend/src/composables/__tests__/useStoryScrollSync.spec.js`

Shared state + scroll listener. Two consumers (band + rail) read `activeRoundIndex`. Implementation uses a module-scoped singleton ref so the same state is shared without `provide/inject`.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/composables/__tests__/useStoryScrollSync.spec.js`:

```js
import { describe, it, expect, afterEach } from 'vitest'
import { useStoryScrollSync, __resetStoryScrollSync } from '../useStoryScrollSync'

afterEach(() => __resetStoryScrollSync())

describe('useStoryScrollSync', () => {
  it('exposes a shared activeRoundIndex across callers', () => {
    const a = useStoryScrollSync()
    const b = useStoryScrollSync()
    a.setActiveRoundIndex(3)
    expect(b.activeRoundIndex.value).toBe(3)
  })

  it('clamps negative or out-of-range indices via setActiveRoundIndex', () => {
    const s = useStoryScrollSync()
    s.setActiveRoundIndex(-5)
    expect(s.activeRoundIndex.value).toBe(0)
    s.setActiveRoundIndex(1.7)
    expect(s.activeRoundIndex.value).toBe(1)  // floor
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/composables/__tests__/useStoryScrollSync.spec.js`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `frontend/src/composables/useStoryScrollSync.js`:

```js
import { ref } from 'vue'

// Module-scoped singletons — shared across all consumers in the app.
let _activeRoundIndex = ref(0)

export function useStoryScrollSync() {
  function setActiveRoundIndex(i) {
    if (typeof i !== 'number' || Number.isNaN(i)) return
    _activeRoundIndex.value = Math.max(0, Math.floor(i))
  }
  return {
    activeRoundIndex: _activeRoundIndex,
    setActiveRoundIndex,
  }
}

// Test helper — do not use in app code.
export function __resetStoryScrollSync() {
  _activeRoundIndex = ref(0)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/composables/__tests__/useStoryScrollSync.spec.js`
Expected: PASS (2/2).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useStoryScrollSync.js frontend/src/composables/__tests__/useStoryScrollSync.spec.js
git commit -m "feat(timeline): add useStoryScrollSync shared state"
```

---

## Task 8: Clustering helper (shared util)

**Files:**
- Modify: `frontend/src/composables/useSimTimeline.js` (export `clusterMoments`)
- Modify: `frontend/src/composables/__tests__/useSimTimeline.spec.js`

Cluster moments whose horizontal % position is within 2% of each other. Used by the band for rendering.

- [ ] **Step 1: Failing test**

Append to spec:

```js
import { clusterMoments } from '../useSimTimeline'

describe('clusterMoments', () => {
  it('groups moments within the threshold and leaves others alone', () => {
    const moments = [
      { id: 'a', roundIndex: 0 },
      { id: 'b', roundIndex: 1 },   // ~10% apart from a with 11 rounds
      { id: 'c', roundIndex: 10 },
    ]
    const clusters = clusterMoments(moments, 11, 0.02)
    expect(clusters).toHaveLength(3)  // none within 2%
  })

  it('collapses nearby moments into a single cluster', () => {
    const moments = [
      { id: 'a', roundIndex: 5 },
      { id: 'b', roundIndex: 5 },
      { id: 'c', roundIndex: 6 },
    ]
    const clusters = clusterMoments(moments, 100, 0.02)  // 1% apart
    expect(clusters).toHaveLength(1)
    expect(clusters[0].items).toHaveLength(3)
  })
})
```

- [ ] **Step 2: Run — verify it fails**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: new tests FAIL (`clusterMoments` is not exported).

- [ ] **Step 3: Implement**

Append to `useSimTimeline.js` (after `useSimTimeline` function):

```js
/**
 * Cluster moments whose horizontal position on a start→end axis is within
 * `threshold` (fractional, e.g. 0.02 = 2%) of the previous cluster's anchor.
 * Input must be sorted by roundIndex. Returns [{ position, items[] }].
 */
export function clusterMoments(moments, roundCount, threshold = 0.02) {
  if (!moments?.length || !roundCount) return []
  const denom = Math.max(1, roundCount - 1)
  const clusters = []
  for (const m of moments) {
    const pos = m.roundIndex / denom
    const last = clusters[clusters.length - 1]
    if (last && Math.abs(pos - last.position) <= threshold) {
      last.items.push(m)
    } else {
      clusters.push({ position: pos, items: [m] })
    }
  }
  return clusters
}
```

- [ ] **Step 4: Run — verify all pass**

Run: `cd frontend && npx vitest run src/composables/__tests__/useSimTimeline.spec.js`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useSimTimeline.js frontend/src/composables/__tests__/useSimTimeline.spec.js
git commit -m "feat(timeline): add clusterMoments positional grouping"
```

---

## Task 9: `StoryTimelineBand.vue` — axis + dots + clustering

**Files:**
- Create: `frontend/src/components/results/StoryTimelineBand.vue`
- Test: `frontend/src/components/results/__tests__/StoryTimelineBand.spec.js`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/results/__tests__/StoryTimelineBand.spec.js`:

```js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StoryTimelineBand from '../StoryTimelineBand.vue'

const baseProps = {
  start: new Date('2026-01-01T00:00:00Z'),
  end:   new Date('2026-01-31T00:00:00Z'),
  roundCount: 5,
  moments: [
    { id: 'a', type: 'market',    roundIndex: 0, title: 'A', detail: '' },
    { id: 'b', type: 'finding',   roundIndex: 2, title: 'B', detail: '' },
    { id: 'c', type: 'coalition', roundIndex: 4, title: 'C', detail: '' },
  ],
}

describe('StoryTimelineBand', () => {
  it('renders one dot per moment when no clustering applies', () => {
    const w = mount(StoryTimelineBand, { props: baseProps })
    expect(w.findAll('[data-timeline-dot]')).toHaveLength(3)
  })

  it('renders nothing when start/end are missing', () => {
    const w = mount(StoryTimelineBand, {
      props: { ...baseProps, start: null, end: null },
    })
    expect(w.find('[data-timeline-band]').exists()).toBe(false)
  })

  it('emits select with the clicked moment id', async () => {
    const w = mount(StoryTimelineBand, { props: baseProps })
    await w.findAll('[data-timeline-dot]')[1].trigger('click')
    expect(w.emitted('select')?.[0]?.[0]).toBe('b')
  })

  it('renders a cluster chip when two moments share a round', async () => {
    const w = mount(StoryTimelineBand, {
      props: {
        ...baseProps,
        moments: [
          { id: 'a', type: 'market',  roundIndex: 2, title: 'A', detail: '' },
          { id: 'b', type: 'finding', roundIndex: 2, title: 'B', detail: '' },
        ],
      },
    })
    expect(w.findAll('[data-timeline-dot]')).toHaveLength(0)
    const chip = w.find('[data-timeline-cluster]')
    expect(chip.exists()).toBe(true)
    expect(chip.text()).toContain('+2')
  })
})
```

- [ ] **Step 2: Run — verify all fail**

Run: `cd frontend && npx vitest run src/components/results/__tests__/StoryTimelineBand.spec.js`
Expected: FAIL.

- [ ] **Step 3: Implement the component**

Create `frontend/src/components/results/StoryTimelineBand.vue`:

```vue
<template>
  <div v-if="start && end && roundCount >= 1"
       data-timeline-band
       class="relative w-full py-6 px-4 bg-ocean-deep border-y border-mist-depth">
    <!-- Date axis -->
    <div class="flex justify-between text-[10px] font-mono uppercase tracking-wider text-mist-slate mb-2">
      <span v-for="tick in ticks" :key="tick.label" :style="{ position: 'absolute', left: tick.pct + '%' }">
        {{ tick.label }}
      </span>
    </div>

    <!-- Baseline -->
    <div class="relative h-[56px]">
      <div class="absolute left-0 right-0 top-1/2 h-px bg-mist-depth"></div>

      <!-- Clusters / dots -->
      <template v-for="cluster in clusters" :key="cluster.position">
        <button
          v-if="cluster.items.length > 1"
          data-timeline-cluster
          :style="{ left: (cluster.position * 100) + '%' }"
          class="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 px-2 py-0.5 rounded-full bg-mist-depth text-[10px] text-mist-foam border border-mist-slate hover:border-ocean-glow transition-colors"
          @click="$emit('clusterClick', cluster)"
        >+{{ cluster.items.length }}</button>

        <button
          v-else
          data-timeline-dot
          :style="{ left: (cluster.position * 100) + '%' }"
          :class="['absolute top-1/2 -translate-x-1/2 -translate-y-1/2 w-3 h-3 rounded-full transition-transform hover:scale-150',
                    typeColor(cluster.items[0].type)]"
          :title="cluster.items[0].title"
          @click="$emit('select', cluster.items[0].id)"
        />
      </template>

      <!-- Scrubber -->
      <div v-if="roundCount > 1"
           class="absolute top-full mt-1 h-0.5 bg-ocean-teal transition-all duration-200"
           :style="{ left: 0, width: progressPct + '%' }" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { clusterMoments } from '@/composables/useSimTimeline'
import { useStoryScrollSync } from '@/composables/useStoryScrollSync'

const props = defineProps({
  start: { type: Date, default: null },
  end: { type: Date, default: null },
  roundCount: { type: Number, default: 0 },
  moments: { type: Array, default: () => [] },
})
defineEmits(['select', 'clusterClick'])

const { activeRoundIndex } = useStoryScrollSync()

const clusters = computed(() => clusterMoments(props.moments, props.roundCount, 0.02))

const progressPct = computed(() => {
  if (props.roundCount <= 1) return 0
  return (activeRoundIndex.value / (props.roundCount - 1)) * 100
})

const ticks = computed(() => {
  if (!props.start || !props.end) return []
  const span = props.end - props.start
  const fmt = pickFormatter(span)
  return [0, 0.25, 0.5, 0.75, 1].map(pct => ({
    pct: pct * 100,
    label: fmt(new Date(props.start.getTime() + span * pct)),
  }))
})

function pickFormatter(spanMs) {
  const days = spanMs / (86400 * 1000)
  if (days <= 2) return d => d.toISOString().slice(11, 16) + 'Z'
  if (days <= 60) return d => d.toISOString().slice(5, 10)
  return d => d.toLocaleString('en-US', { month: 'short', year: '2-digit' })
}

function typeColor(type) {
  switch (type) {
    case 'market':    return 'bg-coral shadow-[0_0_8px_rgba(251,113,133,0.5)]'
    case 'coalition': return 'bg-ocean-teal shadow-[0_0_8px_rgba(34,211,238,0.4)]'
    case 'post':      return 'bg-ocean-glow shadow-[0_0_8px_rgba(34,211,238,0.6)]'
    case 'finding':   return 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.5)]'
    default:          return 'bg-mist-slate'
  }
}
</script>
```

Note: If any of these Tailwind colors (`coral`, `amber-400`) are not in the theme, either add them or substitute with existing tokens. Verify with `grep -n "coral\|amber" frontend/tailwind.config.*`.

- [ ] **Step 4: Run — verify tests pass**

Run: `cd frontend && npx vitest run src/components/results/__tests__/StoryTimelineBand.spec.js`
Expected: PASS (4/4).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/results/StoryTimelineBand.vue frontend/src/components/results/__tests__/StoryTimelineBand.spec.js
git commit -m "feat(timeline): add StoryTimelineBand horizontal component"
```

---

## Task 10: Upgrade `StoryTimeline.vue` — moments on rail

**Files:**
- Modify: `frontend/src/components/results/StoryTimeline.vue`
- Create (or extend existing): `frontend/src/components/results/__tests__/StoryTimeline.spec.js`

- [ ] **Step 1: Failing test**

Create `frontend/src/components/results/__tests__/StoryTimeline.spec.js`:

```js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import StoryTimeline from '../StoryTimeline.vue'

const sections = [
  { id: 'story-hero',     label: 'Q&A' },
  { id: 'story-findings', label: 'Findings' },
]

describe('StoryTimeline', () => {
  it('renders section dots when no moments prop is passed (legacy behavior)', () => {
    const w = mount(StoryTimeline, { props: { sections } })
    expect(w.findAll('[data-section-dot]')).toHaveLength(2)
    expect(w.findAll('[data-moment-dot]')).toHaveLength(0)
  })

  it('renders moment dots when moments prop is passed', () => {
    const w = mount(StoryTimeline, {
      props: {
        sections,
        moments: [
          { id: 'm1', type: 'market',  roundIndex: 0 },
          { id: 'm2', type: 'finding', roundIndex: 4 },
        ],
        roundCount: 5,
      },
    })
    expect(w.findAll('[data-section-dot]')).toHaveLength(2)
    expect(w.findAll('[data-moment-dot]')).toHaveLength(2)
  })
})
```

- [ ] **Step 2: Run — expect failure**

Run: `cd frontend && npx vitest run src/components/results/__tests__/StoryTimeline.spec.js`
Expected: FAIL — current component has no `data-section-dot` / `data-moment-dot` attributes.

- [ ] **Step 3: Update the component**

Replace `frontend/src/components/results/StoryTimeline.vue` with:

```vue
<template>
  <div class="fixed left-6 top-1/2 -translate-y-1/2 z-30 flex flex-col gap-0">
    <template v-for="(section, i) in sections" :key="section.id">
      <div class="flex items-center gap-2.5 py-2 cursor-pointer group" @click="scrollToSection(section.id)">
        <div data-section-dot
             class="w-2 h-2 rounded-full transition-all duration-300 flex-shrink-0"
             :class="i === activeIndex ? 'bg-ocean-glow shadow-[0_0_8px_rgba(34,211,238,0.5)]' : i < activeIndex ? 'bg-ocean-teal' : 'bg-mist-depth'" />
        <span class="text-[11px] text-mist-slate whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity">{{ section.label }}</span>
      </div>
      <div v-if="i < sections.length - 1" class="w-0.5 h-6 ml-[3px] transition-colors duration-300"
        :class="i < activeIndex ? 'bg-ocean-teal' : i === activeIndex ? 'bg-gradient-to-b from-ocean-glow to-ocean-teal' : 'bg-mist-depth'" />
    </template>

    <div v-if="momentsWithPct.length" class="mt-4 pl-1 border-l border-mist-depth flex flex-col gap-1">
      <div v-for="m in momentsWithPct" :key="m.id"
           data-moment-dot
           :title="m.title"
           :class="['w-1.5 h-1.5 rounded-full', typeColor(m.type)]"
           :style="{ marginLeft: '-3px', marginTop: (m.pct * 2) + 'px' }" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useStoryScrollSync } from '@/composables/useStoryScrollSync'

const props = defineProps({
  sections: { type: Array, required: true },
  moments: { type: Array, default: () => [] },
  roundCount: { type: Number, default: 0 },
})

const activeIndex = ref(0)
const { setActiveRoundIndex } = useStoryScrollSync()

const momentsWithPct = computed(() => {
  if (!props.roundCount || props.roundCount < 2) {
    return props.moments.map(m => ({ ...m, pct: 0 }))
  }
  return props.moments.map(m => ({ ...m, pct: (m.roundIndex / (props.roundCount - 1)) * 100 }))
})

function onScroll() {
  for (let i = props.sections.length - 1; i >= 0; i--) {
    const el = document.getElementById(props.sections[i].id)
    if (el && el.getBoundingClientRect().top < window.innerHeight * 0.4) {
      activeIndex.value = i
      if (props.roundCount > 1) {
        const frac = i / Math.max(1, props.sections.length - 1)
        setActiveRoundIndex(Math.round(frac * (props.roundCount - 1)))
      }
      return
    }
  }
  activeIndex.value = 0
  setActiveRoundIndex(0)
}

function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function typeColor(type) {
  switch (type) {
    case 'market':    return 'bg-coral'
    case 'coalition': return 'bg-ocean-teal'
    case 'post':      return 'bg-ocean-glow'
    case 'finding':   return 'bg-amber-400'
    default:          return 'bg-mist-slate'
  }
}

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))
</script>
```

- [ ] **Step 4: Run tests — verify both new and existing pass**

Run: `cd frontend && npx vitest run src/components/results/__tests__/StoryTimeline.spec.js`
Expected: PASS (2/2).

Run any existing usage tests too:
```bash
cd frontend && npx vitest run src/components/
```
Expected: no regressions.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/results/StoryTimeline.vue frontend/src/components/results/__tests__/StoryTimeline.spec.js
git commit -m "feat(timeline): add moments prop to StoryTimeline rail"
```

---

## Task 11: Wire into `SimulationResults.vue`

**Files:**
- Modify: `frontend/src/views/SimulationResults.vue`
- Modify: `frontend/src/composables/useSimulationData.js` (optional — only if cleaner to pull in sim-data here)

The story view currently uses only `structured` from the job payload. Market/post/trajectory data lives in MinIO sim-data; currently only `DataDashboard` fetches it. We'll fetch it once at the view level and share.

- [ ] **Step 1: Inspect current imports in `SimulationResults.vue`**

Run: `head -n 170 frontend/src/views/SimulationResults.vue`

Confirm: existing imports of `ReportToc`, `QuestionAnswerHero`, `SimScaleFooter`, `structured`, `viewMode`. Note the `import { getSimData } from '...'` used in `DataDashboard.vue`. You'll add the same import here.

- [ ] **Step 2: Add sim-data loading state**

In the `<script setup>` block of `SimulationResults.vue`, import:

```js
import { ref, computed, onMounted, watch } from 'vue'
import { getSimData } from '@/api/jobs'
import { useSimTimeline } from '@/composables/useSimTimeline'
import StoryTimelineBand from '@/components/results/StoryTimelineBand.vue'
```

Add state (near other refs, e.g. after `const viewMode = ref('story')`):

```js
const marketCurves = ref([])
const topPosts = ref([])
const agentTrajectories = ref([])

async function loadSimData() {
  if (!job.value?.sim_data_available) return
  try {
    const { files } = await getSimData(job.value.id)
    async function fetchJson(url) {
      if (!url) return null
      const resp = await fetch(url)
      return resp.ok ? resp.json() : null
    }
    const [mc, tp, at] = await Promise.all([
      fetchJson(files['market_curves.json']),
      fetchJson(files['top_posts.json']),
      fetchJson(files['agent_trajectories.json']),
    ])
    marketCurves.value = mc || []
    topPosts.value = tp || []
    agentTrajectories.value = at || []
  } catch (e) {
    console.error('Failed to load timeline sim-data:', e)
  }
}

watch(() => job.value?.sim_data_available, (v) => { if (v) loadSimData() }, { immediate: true })
```

- [ ] **Step 3: Build the timeline**

Add (below the sim-data refs):

```js
const timeline = computed(() => useSimTimeline({
  startedAt: job.value?.created_at,
  forecastDays: job.value?.forecast_days,
  roundCount: computeRoundCount(marketCurves.value, agentTrajectories.value),
  structured: structured.value,
  marketCurves: marketCurves.value,
  topPosts: topPosts.value,
  agentTrajectories: agentTrajectories.value,
}))

function computeRoundCount(mc, at) {
  const fromMarkets = Math.max(0, ...((mc || []).flatMap(m => (m.points || []).map(p => p.round_num || 0))))
  const fromAgents  = Math.max(0, ...((at || []).flatMap(a => (a.stance_per_round || []).map(s => s.round_num || 0))))
  return Math.max(fromMarkets, fromAgents)
}
```

- [ ] **Step 4: Render `StoryTimelineBand` after hero**

Find the `<div v-if="viewMode === 'story'" ...>` block (around line 24). After `<QuestionAnswerHero>` / `story-hero` div and before `story-findings`, insert:

```vue
<StoryTimelineBand
  v-if="timeline.start"
  :start="timeline.start"
  :end="timeline.end"
  :roundCount="timeline.roundDates.length"
  :moments="timeline.moments"
  @select="onTimelineSelect"
/>
```

- [ ] **Step 5: Pass moments into the existing `StoryTimeline` rail**

Find the `<ReportToc :items="storySections" />` usage (around line 25). If `ReportToc` wraps `StoryTimeline`, extend its props; if `StoryTimeline` is rendered separately, locate it with `grep -n "StoryTimeline" frontend/src/views/SimulationResults.vue` and pass:

```vue
<StoryTimeline
  :sections="storySections"
  :moments="timeline.moments"
  :roundCount="timeline.roundDates.length"
/>
```

If `ReportToc` currently wraps `StoryTimeline`, either (a) open `ReportToc.vue` and forward the two new props, or (b) render `StoryTimeline` directly and remove `ReportToc` if it's a thin wrapper. Match the style of the existing code; don't restructure unnecessarily.

- [ ] **Step 6: Implement `onTimelineSelect`**

Add the click handler in `<script setup>`:

```js
function onTimelineSelect(momentId) {
  const moment = timeline.value.moments.find(m => m.id === momentId)
  if (!moment) return
  if (moment.refId) {
    const el = document.getElementById(moment.refId)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' })
      el.classList.add('ring-2', 'ring-ocean-glow')
      setTimeout(() => el.classList.remove('ring-2', 'ring-ocean-glow'), 1500)
    }
  }
}
```

- [ ] **Step 7: Add `id="story-finding-<i>"` to each rendered finding**

Find the findings render block (around `v-for="(f, i) in structured.findings"`). Ensure each rendered wrapper has:

```vue
:id="`story-finding-${i}`"
```

This matches the `refId` pattern in Task 4.

- [ ] **Step 8: Manual verification**

Start the dev server:
```bash
cd frontend && npm run dev
```

Open a completed simulation's story view. Verify:
- Horizontal band renders below the Q&A hero
- Dots appear for market/finding/coalition/post moments
- Clicking a finding dot scrolls to that finding and briefly highlights it
- Left rail still works; new secondary moment dots appear below the section dots
- With a sim where `sim_data_available` is false, band still renders with findings-only moments

Also verify Data view (`?view=data` or toolbar toggle) still renders correctly — `DataDashboard` does its own sim-data fetch; our additional fetch should not conflict.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/views/SimulationResults.vue frontend/src/components/results/StoryTimeline.vue
git commit -m "feat(timeline): wire StoryTimelineBand into SimulationResults

Loads market_curves/top_posts/agent_trajectories on story view, builds
a timeline, and renders horizontal band + date-aware vertical rail."
```

---

## Task 12: Verify full test + lint

- [ ] **Step 1: Run all frontend tests**

Run: `cd frontend && npm test`
Expected: all pass.

- [ ] **Step 2: Run all backend tests for the jobs module**

Run: `pytest tests/jobs/ -v`
Expected: all pass.

- [ ] **Step 3: Ruff / linters (if configured for pre-commit)**

Run: `ruff check saas/` (if ruff is installed) — expected: no new issues.
Run: `cd frontend && npm run build` — expected: build succeeds with no new warnings.

- [ ] **Step 4: Final commit (if any lint fixups were needed)**

Only if earlier steps introduced lint fixes:

```bash
git add -p
git commit -m "chore: lint/format follow-ups for timeline feature"
```

---

## Known Follow-ups (out of scope, but documented)

- **Per-round enrichment events (moment type E):** requires engine changes — not in this plan.
- **Richer coalition semantics:** v1 uses plurality-stance flips only. A later pass can use `named_coalitions` with per-round membership to detect formation/dissolution.
- **Agent-authored in-world dates:** deferred. Today the mapping is a uniform stretch; agents don't emit dates.
- **Mobile layout:** band is implemented desktop-first. Responsive passes can come after the desktop experience is validated.

---

## Self-Review Notes

Reviewed against spec `2026-04-23-story-timeline-design.md`:

- Date mapping (uniform stretch): Task 2. ✓
- Moment type: market: Task 3. ✓
- Moment type: finding (phase-anchored): Task 4. ✓
- Moment type: post (top engagement per round): Task 5. ✓
- Moment type: coalition: Task 6 (plurality-stance flip; simpler than spec's "stakeholder group flips," documented as follow-up). ⚠️ Scope-reduced — called out in Known Follow-ups.
- `useSimTimeline` pure composable: Tasks 2–6, 8. ✓
- `useStoryScrollSync` shared state: Task 7. ✓
- `StoryTimelineBand.vue`: Task 9. ✓
- `StoryTimeline.vue` upgrade: Task 10. ✓
- Integration in `SimulationResults.vue`: Task 11. ✓
- Clustering: Task 8, rendered in Task 9. ✓
- Error/empty states (no data → no band, missing horizon → fallback): handled in Tasks 2/9. ✓
- Backend change for `forecast_days` exposure: Task 1 (new, required — was an open verification item in the spec). ✓
- Testing coverage: unit tests for composable + both components. ✓
