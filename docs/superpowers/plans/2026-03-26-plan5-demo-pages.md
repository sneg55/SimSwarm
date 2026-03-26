# Plan 5: Demo Pages

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build 4-5 public demo result pages (no login required) showing pre-run MiroFish simulation results as the marketing hook, plus a landing page that links to them.

**Architecture:** Static JSON snapshot files stored in `demos/` directory. A weekly cron script re-runs each demo sim and updates the snapshots. Frontend renders demos using the same ReportViewer and ChatReplay components from Plan 4.

**Tech Stack:** Vue 3 (existing components), JSON static data, Python script for re-runs

**Depends on:** Plan 1 (MiroFish adapter), Plan 4 (ReportViewer, ChatReplay components)

**Spec reference:** `docs/superpowers/specs/2026-03-26-mirofish-hosted-mvp-design.md` — Appendix C, Flow 1

---

## File Structure

```
demos/
├── iran-war-us-china.json
├── tesla-earnings.json
├── dream-red-chamber.json
├── eu-ai-act.json
└── bitcoin-halving.json
frontend/
├── src/
│   ├── api/
│   │   └── demos.js                 # Fetch demo JSON
│   ├── views/
│   │   ├── Landing.vue              # Marketing page + demo links
│   │   └── DemoResult.vue           # Public demo result page
│   └── router/
│       └── index.js                 # Add /demo/:slug routes
├── tests/
│   ├── views/
│   │   └── DemoResult.spec.js
│   └── components/
│       └── DemoCard.spec.js
infra/
└── scripts/
    └── refresh_demos.py             # Weekly demo re-run script
tests/
└── test_refresh_demos.py            # Script test
```

---

### Task 1: Demo JSON Schema + Seed Data

**Files:**
- Create: `demos/iran-war-us-china.json`
- Create: `demos/tesla-earnings.json`
- Create: `demos/dream-red-chamber.json`
- Create: `demos/eu-ai-act.json`
- Create: `demos/bitcoin-halving.json`

- [ ] **Step 1: Define demo JSON schema and create placeholder files**

Each demo JSON follows this schema:

```json
{
  "slug": "iran-war-us-china",
  "title": "US vs China Public Opinion on Iran Escalation",
  "description": "Predicting how public opinion shifts across US and Chinese social media over 30 simulated days",
  "seed_summary": "CNN breaking news: Iran tensions escalate as US and China take opposing stances...",
  "goal": "Predict US vs China public opinion on Iran escalation over 30 days",
  "tier": "medium",
  "agent_count": 1000,
  "rounds": 100,
  "report_markdown": "# Prediction Report\n\n## Executive Summary\n\nThis is a placeholder report...",
  "chat_log": [
    {"agent_name": "Agent_US_001", "action_type": "CREATE_POST", "action_args": {"content": "Concerned about escalation..."}, "round": 1},
    {"agent_name": "Agent_CN_042", "action_type": "CREATE_POST", "action_args": {"content": "Supporting diplomatic approach..."}, "round": 1}
  ],
  "generated_at": "2026-03-26T00:00:00Z"
}
```

Create 5 placeholder files following this schema. Use descriptive placeholder content that demonstrates what a real simulation would produce.

```bash
mkdir -p demos
```

```json
// demos/iran-war-us-china.json
{
  "slug": "iran-war-us-china",
  "title": "US vs China Public Opinion on Iran Escalation",
  "description": "Simulating 1,000 agents across US and Chinese social media to predict opinion shifts over 30 days",
  "seed_summary": "Breaking: Iran nuclear talks collapse as US imposes new sanctions. China condemns unilateral action.",
  "goal": "Predict US vs China public opinion on Iran escalation over 30 days",
  "tier": "medium",
  "agent_count": 1000,
  "rounds": 100,
  "report_markdown": "# Prediction: US vs China Public Opinion on Iran\n\n## Executive Summary\n\nPlaceholder — will be replaced by actual MiroFish simulation output.\n\n## Key Findings\n\n1. US opinion polarizes along partisan lines within 48 hours\n2. Chinese social media shows unified support for diplomatic approach\n3. Cross-platform influence detected via shared news articles\n\n## Detailed Analysis\n\nPending actual simulation run.",
  "chat_log": [
    {"agent_name": "US_Analyst_001", "action_type": "CREATE_POST", "action_args": {"content": "New sanctions on Iran could backfire. Markets already pricing in risk."}, "round": 1},
    {"agent_name": "CN_Observer_042", "action_type": "CREATE_POST", "action_args": {"content": "Diplomatic channels must remain open. Unilateral sanctions harm global stability."}, "round": 1},
    {"agent_name": "US_Trader_017", "action_type": "CREATE_POST", "action_args": {"content": "Oil futures spiking. This is the play."}, "round": 2}
  ],
  "generated_at": "2026-03-26T00:00:00Z"
}
```

Create similar files for the other 4 demos with appropriate placeholder content:
- `demos/tesla-earnings.json` — Tesla Q1 earnings market sentiment
- `demos/dream-red-chamber.json` — Lost ending of Dream of the Red Chamber
- `demos/eu-ai-act.json` — EU AI Act industry reaction
- `demos/bitcoin-halving.json` — Crypto community sentiment post-halving

- [ ] **Step 2: Commit**

```bash
git add demos/
git commit -m "feat: add placeholder demo JSON files for 5 public demos"
```

---

### Task 2: Demo API Client + DemoResult View

**Files:**
- Create: `frontend/src/api/demos.js`
- Create: `frontend/src/views/DemoResult.vue`
- Create: `frontend/tests/views/DemoResult.spec.js`

- [ ] **Step 1: Write DemoResult test**

```js
// frontend/tests/views/DemoResult.spec.js
import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import DemoResult from '../../src/views/DemoResult.vue'

// Mock the demos API
vi.mock('../../src/api/demos', () => ({
  getDemo: vi.fn().mockResolvedValue({
    slug: 'test-demo',
    title: 'Test Demo',
    description: 'A test demo',
    seed_summary: 'Test seed',
    goal: 'Test goal',
    report_markdown: '# Test Report\n\nFindings here.',
    chat_log: [
      { agent_name: 'Agent_1', action_type: 'CREATE_POST', action_args: { content: 'Hello world' } },
    ],
  }),
}))

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/demo/:slug', component: DemoResult }],
})

describe('DemoResult', () => {
  it('renders demo title and report', async () => {
    router.push('/demo/test-demo')
    await router.isReady()

    const wrapper = mount(DemoResult, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Test Demo')
    expect(wrapper.text()).toContain('Test Report')
  })

  it('renders agent chat replay', async () => {
    router.push('/demo/test-demo')
    await router.isReady()

    const wrapper = mount(DemoResult, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Agent_1')
    expect(wrapper.text()).toContain('Hello world')
  })

  it('shows CTA to sign up', async () => {
    router.push('/demo/test-demo')
    await router.isReady()

    const wrapper = mount(DemoResult, {
      global: { plugins: [router] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Run your own simulation')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run tests/views/DemoResult.spec.js
```

Expected: FAIL — modules not found.

- [ ] **Step 3: Implement demo API client**

```js
// frontend/src/api/demos.js
const DEMO_SLUGS = [
  'iran-war-us-china',
  'tesla-earnings',
  'dream-red-chamber',
  'eu-ai-act',
  'bitcoin-halving',
]

export async function getDemo(slug) {
  const resp = await fetch(`/demos/${slug}.json`)
  if (!resp.ok) throw new Error(`Demo not found: ${slug}`)
  return resp.json()
}

export async function listDemos() {
  const demos = await Promise.all(
    DEMO_SLUGS.map(async (slug) => {
      try {
        return await getDemo(slug)
      } catch {
        return null
      }
    })
  )
  return demos.filter(Boolean)
}
```

- [ ] **Step 4: Implement DemoResult view**

```vue
<!-- frontend/src/views/DemoResult.vue -->
<template>
  <div class="max-w-4xl mx-auto py-8 px-4">
    <div v-if="demo" class="space-y-8">
      <div>
        <div class="text-sm text-blue-600 font-medium mb-2">Public Demo</div>
        <h1 class="text-3xl font-bold">{{ demo.title }}</h1>
        <p class="text-gray-500 mt-2">{{ demo.description }}</p>
      </div>

      <div class="bg-gray-100 p-4 rounded-lg">
        <div class="text-sm font-medium text-gray-700 mb-1">Seed Material</div>
        <p class="text-gray-600">{{ demo.seed_summary }}</p>
      </div>

      <div class="bg-white p-8 rounded-lg shadow">
        <h2 class="text-xl font-bold mb-4">Prediction Report</h2>
        <ReportViewer :markdown="demo.report_markdown" />
      </div>

      <div>
        <h2 class="text-xl font-bold mb-4">Agent Activity Replay</h2>
        <ChatReplay :messages="demo.chat_log" />
      </div>

      <div class="bg-blue-50 border border-blue-200 rounded-lg p-6 text-center">
        <h3 class="text-lg font-bold text-blue-900">Run your own simulation</h3>
        <p class="text-blue-700 mt-1">Buy credits and run MiroFish on any topic you choose.</p>
        <router-link to="/register"
          class="inline-block mt-4 px-6 py-2 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700">
          Get Started
        </router-link>
      </div>
    </div>

    <div v-else class="text-center py-16 text-gray-400">Loading demo...</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getDemo } from '../api/demos'
import ReportViewer from '../components/ReportViewer.vue'
import ChatReplay from '../components/ChatReplay.vue'

const route = useRoute()
const demo = ref(null)

onMounted(async () => {
  demo.value = await getDemo(route.params.slug)
})
</script>
```

- [ ] **Step 5: Add demo routes to router**

Add to `frontend/src/router/index.js` routes array:

```js
{ path: '/demo/:slug', name: 'demo', component: () => import('../views/DemoResult.vue') },
```

- [ ] **Step 6: Run tests**

```bash
cd frontend && npx vitest run tests/views/DemoResult.spec.js
```

Expected: 3 passed.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/demos.js frontend/src/views/DemoResult.vue frontend/src/router/index.js frontend/tests/
git commit -m "feat: add DemoResult view with report viewer and chat replay"
```

---

### Task 3: Landing Page

**Files:**
- Modify: `frontend/src/views/Landing.vue`
- Create: `frontend/src/components/DemoCard.vue`
- Create: `frontend/tests/components/DemoCard.spec.js`

- [ ] **Step 1: Write DemoCard test**

```js
// frontend/tests/components/DemoCard.spec.js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import DemoCard from '../../src/components/DemoCard.vue'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/demo/:slug', component: { template: '<div />' } }],
})

describe('DemoCard', () => {
  it('renders demo title and description', () => {
    const wrapper = mount(DemoCard, {
      props: {
        slug: 'test',
        title: 'Test Demo',
        description: 'A test simulation',
      },
      global: { plugins: [router] },
    })
    expect(wrapper.text()).toContain('Test Demo')
    expect(wrapper.text()).toContain('A test simulation')
  })

  it('links to demo page', () => {
    const wrapper = mount(DemoCard, {
      props: {
        slug: 'iran-war-us-china',
        title: 'Iran Demo',
        description: 'Test',
      },
      global: { plugins: [router] },
    })
    expect(wrapper.find('a').attributes('href')).toBe('/demo/iran-war-us-china')
  })
})
```

- [ ] **Step 2: Implement DemoCard**

```vue
<!-- frontend/src/components/DemoCard.vue -->
<template>
  <router-link :to="`/demo/${slug}`"
    class="block p-6 bg-white rounded-lg shadow hover:shadow-md transition border border-gray-100">
    <h3 class="text-lg font-bold text-gray-900">{{ title }}</h3>
    <p class="text-gray-500 mt-2 text-sm">{{ description }}</p>
    <span class="inline-block mt-3 text-blue-600 text-sm font-medium">View results &rarr;</span>
  </router-link>
</template>

<script setup>
defineProps({
  slug: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
})
</script>
```

- [ ] **Step 3: Implement Landing page**

```vue
<!-- frontend/src/views/Landing.vue -->
<template>
  <div>
    <!-- Hero -->
    <section class="py-20 text-center">
      <h1 class="text-5xl font-bold text-gray-900">
        Predict Anything with <span class="text-blue-600">Swarm Intelligence</span>
      </h1>
      <p class="mt-4 text-xl text-gray-500 max-w-2xl mx-auto">
        Run thousands of AI agents on any topic. Get prediction reports powered by MiroFish — no setup required.
      </p>
      <div class="mt-8 flex gap-4 justify-center">
        <router-link to="/register"
          class="px-6 py-3 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700">
          Get Started
        </router-link>
        <a href="#demos" class="px-6 py-3 border border-gray-300 rounded-md font-medium hover:bg-gray-50">
          See Live Demos
        </a>
      </div>
    </section>

    <!-- Demo Section -->
    <section id="demos" class="py-16 bg-gray-50">
      <div class="max-w-4xl mx-auto px-4">
        <h2 class="text-3xl font-bold text-center mb-8">Live Demo Results</h2>
        <p class="text-center text-gray-500 mb-10">
          Real MiroFish simulations — no login required. See what swarm intelligence can do.
        </p>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <DemoCard
            v-for="demo in demos"
            :key="demo.slug"
            :slug="demo.slug"
            :title="demo.title"
            :description="demo.description"
          />
        </div>
      </div>
    </section>

    <!-- Pricing -->
    <section class="py-16">
      <div class="max-w-4xl mx-auto px-4 text-center">
        <h2 class="text-3xl font-bold mb-8">Simple Credit-Based Pricing</h2>
        <div class="grid grid-cols-3 gap-6">
          <div v-for="pack in packs" :key="pack.name" class="p-6 bg-white rounded-lg shadow border">
            <div class="text-lg font-bold">{{ pack.name }}</div>
            <div class="text-3xl font-bold mt-2">${{ pack.price }}</div>
            <div class="text-gray-500 mt-1">{{ pack.credits }} credits</div>
            <div class="text-sm text-gray-400 mt-2">{{ pack.description }}</div>
          </div>
        </div>
        <router-link to="/register" class="inline-block mt-8 px-6 py-3 bg-blue-600 text-white rounded-md font-medium hover:bg-blue-700">
          Buy Credits & Start
        </router-link>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listDemos } from '../api/demos'
import DemoCard from '../components/DemoCard.vue'

const demos = ref([])

const packs = [
  { name: 'Starter', credits: 100, price: 19, description: '3-4 small simulations' },
  { name: 'Pro', credits: 500, price: 79, description: '15-20 medium simulations' },
  { name: 'Heavy', credits: 2000, price: 249, description: 'Large-scale or frequent use' },
]

onMounted(async () => {
  demos.value = await listDemos()
})
</script>
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && npx vitest run
```

Expected: All tests pass (previous + 2 DemoCard tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/Landing.vue frontend/src/components/DemoCard.vue frontend/tests/
git commit -m "feat: add Landing page with demo cards and pricing section"
```

---

### Task 4: Demo Refresh Script

**Files:**
- Create: `infra/scripts/refresh_demos.py`
- Create: `tests/test_refresh_demos.py`

- [ ] **Step 1: Write refresh script test**

```python
# tests/test_refresh_demos.py
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from infra.scripts.refresh_demos import (
    DEMO_CONFIGS,
    generate_demo_snapshot,
    validate_snapshot,
)


def test_demo_configs_defined():
    assert len(DEMO_CONFIGS) == 5
    slugs = [d["slug"] for d in DEMO_CONFIGS]
    assert "iran-war-us-china" in slugs
    assert "tesla-earnings" in slugs
    assert "dream-red-chamber" in slugs
    assert "eu-ai-act" in slugs
    assert "bitcoin-halving" in slugs


def test_each_config_has_required_fields():
    required = {"slug", "title", "description", "seed_summary", "seed_source", "goal", "tier"}
    for config in DEMO_CONFIGS:
        missing = required - set(config.keys())
        assert not missing, f"Config {config['slug']} missing: {missing}"


def test_validate_snapshot_valid():
    snapshot = {
        "slug": "test",
        "title": "Test",
        "description": "Test desc",
        "seed_summary": "Test seed",
        "goal": "Test goal",
        "tier": "small",
        "agent_count": 100,
        "rounds": 50,
        "report_markdown": "# Report",
        "chat_log": [{"agent_name": "A1", "action_type": "POST", "action_args": {"content": "hi"}}],
        "generated_at": "2026-03-26T00:00:00Z",
    }
    assert validate_snapshot(snapshot) is True


def test_validate_snapshot_missing_report():
    snapshot = {"slug": "test", "report_markdown": ""}
    assert validate_snapshot(snapshot) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_refresh_demos.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement refresh script**

```python
# infra/__init__.py
```

```python
# infra/scripts/__init__.py
```

```python
# infra/scripts/refresh_demos.py
"""
Weekly demo refresh script.

Runs each demo simulation on the MiroFish backend and exports results
to static JSON files in demos/ directory.

Usage: python -m infra.scripts.refresh_demos [--dry-run]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DEMOS_DIR = Path(__file__).parent.parent.parent / "demos"

DEMO_CONFIGS = [
    {
        "slug": "iran-war-us-china",
        "title": "US vs China Public Opinion on Iran Escalation",
        "description": "Simulating 1,000 agents across US and Chinese social media to predict opinion shifts over 30 days",
        "seed_summary": "Breaking: Iran nuclear talks collapse as US imposes new sanctions. China condemns unilateral action.",
        "seed_source": "public-domain-news",
        "goal": "Predict US vs China public opinion on Iran escalation over 30 days",
        "tier": "medium",
    },
    {
        "slug": "tesla-earnings",
        "title": "Market Sentiment After Tesla Q1 Earnings",
        "description": "Simulating 500 financial analyst and retail investor agents reacting to Tesla's Q1 2026 earnings",
        "seed_summary": "Tesla reports Q1 2026 earnings: revenue beats expectations, delivery numbers miss.",
        "seed_source": "sec-10k-excerpt",
        "goal": "Predict market sentiment and price movement after Tesla Q1 earnings release",
        "tier": "medium",
    },
    {
        "slug": "dream-red-chamber",
        "title": "Predicting the Lost Ending of Dream of the Red Chamber",
        "description": "Simulating 200 literary scholar agents debating and predicting the original lost ending",
        "seed_summary": "Chapters 1-80 of Dream of the Red Chamber by Cao Xueqin (public domain).",
        "seed_source": "gutenberg",
        "goal": "Predict the original lost ending of Dream of the Red Chamber based on first 80 chapters",
        "tier": "small",
    },
    {
        "slug": "eu-ai-act",
        "title": "Industry Reaction to EU AI Act Enforcement",
        "description": "Simulating 800 tech executives, regulators, and researchers reacting to EU AI Act coming into force",
        "seed_summary": "EU AI Act enforcement begins: high-risk AI systems must comply by March 2026.",
        "seed_source": "public-policy-doc",
        "goal": "Predict tech industry response to EU AI Act enforcement over 60 days",
        "tier": "medium",
    },
    {
        "slug": "bitcoin-halving",
        "title": "Crypto Community Sentiment Post-Halving",
        "description": "Simulating 1,500 crypto traders, miners, and analysts reacting to Bitcoin's next halving event",
        "seed_summary": "Bitcoin halving reduces block reward from 3.125 to 1.5625 BTC. Mining profitability concerns mount.",
        "seed_source": "crypto-news-roundup",
        "goal": "Predict crypto community sentiment and BTC price expectations 30 days post-halving",
        "tier": "medium",
    },
]


def validate_snapshot(snapshot: dict) -> bool:
    """Validate that a demo snapshot has all required fields and non-empty report."""
    required = {"slug", "report_markdown", "chat_log"}
    if not required.issubset(snapshot.keys()):
        return False
    if not snapshot.get("report_markdown", "").strip():
        return False
    return True


def generate_demo_snapshot(config: dict) -> dict:
    """
    Run a MiroFish simulation for the given demo config and return a snapshot.

    In production, this calls the MiroFish adapter to run the full pipeline.
    For now, returns the existing placeholder content.
    """
    # TODO: Replace with actual MiroFish adapter call once GPU orchestration is ready
    # This will be: adapter.run_simulation(seed, goal, tier) -> results
    existing_file = DEMOS_DIR / f"{config['slug']}.json"
    if existing_file.exists():
        return json.loads(existing_file.read_text())

    return {
        "slug": config["slug"],
        "title": config["title"],
        "description": config["description"],
        "seed_summary": config["seed_summary"],
        "goal": config["goal"],
        "tier": config["tier"],
        "agent_count": 0,
        "rounds": 0,
        "report_markdown": "# Pending\n\nThis demo is waiting for its first simulation run.",
        "chat_log": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def refresh_all(dry_run: bool = False) -> None:
    """Refresh all demo snapshots."""
    DEMOS_DIR.mkdir(exist_ok=True)

    for config in DEMO_CONFIGS:
        print(f"Refreshing demo: {config['slug']}...")
        snapshot = generate_demo_snapshot(config)

        if not validate_snapshot(snapshot):
            print(f"  WARNING: Invalid snapshot for {config['slug']}, skipping")
            continue

        snapshot["generated_at"] = datetime.now(timezone.utc).isoformat()

        if dry_run:
            print(f"  [DRY RUN] Would write {config['slug']}.json")
        else:
            output_file = DEMOS_DIR / f"{config['slug']}.json"
            output_file.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))
            print(f"  Written to {output_file}")

    print("Done.")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    refresh_all(dry_run=dry_run)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_refresh_demos.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add infra/ tests/test_refresh_demos.py
git commit -m "feat: add demo refresh script with validation and 5 demo configs"
```

---

### Task 5: Configure Vite to Serve Demo JSON

**Files:**
- Modify: `frontend/vite.config.js`

- [ ] **Step 1: Update vite config to serve demos directory**

Add to `frontend/vite.config.js` server config:

```js
// Add to server block in vite.config.js
proxy: {
  '/api': {
    target: 'http://localhost:8080',
    changeOrigin: true,
  },
},
// Serve demo JSON files from repo root
fs: {
  allow: ['..'],  // Allow serving files from parent directory
},
```

Also add a public directory alias or a custom middleware for `/demos/` to point to `../demos/`.

For production, these JSON files would be served from S3 or bundled.

- [ ] **Step 2: Verify demos load in dev**

```bash
cd frontend && npm run dev &
curl http://localhost:3000/demos/iran-war-us-china.json | head -5
```

Expected: Returns the JSON content.

- [ ] **Step 3: Commit**

```bash
git add frontend/vite.config.js
git commit -m "feat: configure Vite to serve demo JSON files in dev mode"
```

---

## Test Suite Summary (After Plan 5)

| File | Tests | What it covers |
|------|-------|----------------|
| `frontend/tests/views/DemoResult.spec.js` | 3 | Demo rendering, chat replay, CTA |
| `frontend/tests/components/DemoCard.spec.js` | 2 | Card rendering, link target |
| `tests/test_refresh_demos.py` | 4 | Config completeness, validation, schema |
| **Plan 5 Total** | **9** | |
| *(Plans 1-4)* | 87 | |
| **Grand Total** | **96** | |
