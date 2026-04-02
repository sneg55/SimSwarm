# Live Pod Progress Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface round counts and a live agent feed from the GPU pod to the simulation status page while a job is running.

**Architecture:** Add a `live_status` JSONB column to `simulation_jobs`. The Celery worker polls the pod's `/logs` and `/partial_chat` endpoints every 20s, extracts round counts and log milestones into `live_status`, and writes to DB via sync psycopg2. The frontend's existing 3s `getJob` poll picks up the data and renders a Rounds row + a `LiveActivity.vue` component.

**Tech Stack:** Python/SQLAlchemy (backend), Alembic (migrations), Flask (pod API), Vue 3/Vitest (frontend)

---

## File Map

| Action | File |
|--------|------|
| Create | `alembic/versions/n5o6p7q8r9s0_add_live_status.py` |
| Modify | `saas/models/job.py` |
| Modify | `saas/schemas/jobs.py` |
| Create | `tests/test_live_status_extraction.py` |
| Modify | `saas/workers/persistence.py` |
| Modify | `saas/workers/job_runner.py` |
| Modify | `infra/docker/worker_api.py` |
| Create | `frontend/src/components/LiveActivity.vue` |
| Create | `frontend/src/components/__tests__/LiveActivity.test.js` |
| Modify | `frontend/src/views/SimulationStatus.vue` |

---

## Task 1: DB Migration, Model Column, Schema Field

**Files:**
- Create: `alembic/versions/n5o6p7q8r9s0_add_live_status.py`
- Modify: `saas/models/job.py`
- Modify: `saas/schemas/jobs.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_live_status_extraction.py` — just the schema test for now:

```python
"""Tests for live_status column and schema."""
import pytest
from saas.models.job import SimulationJob
from saas.schemas.jobs import JobResponse


def test_job_model_has_live_status_column():
    """SimulationJob must have a live_status mapped column."""
    cols = [c.key for c in SimulationJob.__mapper__.columns]
    assert "live_status" in cols


def test_job_response_schema_includes_live_status():
    """JobResponse Pydantic schema must include live_status field."""
    fields = JobResponse.model_fields
    assert "live_status" in fields
    assert fields["live_status"].is_required() is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /path/to/repo && pytest tests/test_live_status_extraction.py::test_job_model_has_live_status_column tests/test_live_status_extraction.py::test_job_response_schema_includes_live_status -v
```

Expected: FAIL — `AssertionError: assert "live_status" in [...]`

- [ ] **Step 3: Add column to model**

In `saas/models/job.py`, add `JSON` to the import line and add the column at the end of `SimulationJob`:

```python
# Change import line from:
from sqlalchemy import String, Text, Integer, DateTime, Enum
# to:
from sqlalchemy import String, Text, Integer, DateTime, Enum, JSON
```

Add after `sim_data_available`:

```python
    live_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 4: Add field to JobResponse schema**

In `saas/schemas/jobs.py`, add to `JobResponse` after `sim_data_available`:

```python
    live_status: dict | None = None
```

- [ ] **Step 5: Run model/schema tests to verify they pass**

```bash
pytest tests/test_live_status_extraction.py::test_job_model_has_live_status_column tests/test_live_status_extraction.py::test_job_response_schema_includes_live_status -v
```

Expected: PASS

- [ ] **Step 6: Create Alembic migration**

Create `alembic/versions/n5o6p7q8r9s0_add_live_status.py`:

```python
"""add live_status column to simulation_jobs

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_jobs", sa.Column("live_status", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_jobs", "live_status")
```

- [ ] **Step 7: Verify migration runs against in-memory SQLite (used in tests)**

```bash
pytest tests/ -x -q 2>&1 | head -30
```

Expected: existing tests still pass (no `live_status` breakage).

- [ ] **Step 8: Commit**

```bash
git add alembic/versions/n5o6p7q8r9s0_add_live_status.py saas/models/job.py saas/schemas/jobs.py tests/test_live_status_extraction.py
git commit -m "feat: add live_status column to simulation_jobs"
```

---

## Task 2: Log Extraction Helper

**Files:**
- Modify: `saas/workers/job_runner.py` (add `_extract_live_status`)
- Modify: `tests/test_live_status_extraction.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_live_status_extraction.py`:

```python
from saas.workers.job_runner import _extract_live_status


def test_extract_round_from_log_line():
    lines = ["[pipeline] round=47 complete", "[pipeline] Building agent profiles"]
    result = _extract_live_status(lines)
    assert result["round"] == 47


def test_extract_round_variant_spacing():
    lines = ["[pipeline] Running simulation round 12"]
    result = _extract_live_status(lines)
    assert result["round"] == 12


def test_extract_keeps_highest_round():
    lines = ["[pipeline] round=10 complete", "[pipeline] round=47 complete"]
    result = _extract_live_status(lines)
    assert result["round"] == 47


def test_extract_no_round_when_absent():
    lines = ["[pipeline] Building knowledge graph"]
    result = _extract_live_status(lines)
    assert "round" not in result


def test_extract_filters_http_noise():
    lines = ["GET /health HTTP/1.1", "[pipeline] 12 entities extracted", "POST /job HTTP/1.1"]
    result = _extract_live_status(lines)
    assert result["log_lines"] == ["[pipeline] 12 entities extracted"]


def test_extract_filters_blank_lines():
    lines = ["", "   ", "[pipeline] Building knowledge graph"]
    result = _extract_live_status(lines)
    assert result["log_lines"] == ["[pipeline] Building knowledge graph"]


def test_extract_filters_short_lines():
    lines = ["ok", "[pipeline] Building knowledge graph"]
    result = _extract_live_status(lines)
    assert result["log_lines"] == ["[pipeline] Building knowledge graph"]


def test_extract_max_3_log_lines():
    lines = [f"[pipeline] step number {i} complete here" for i in range(10)]
    result = _extract_live_status(lines)
    assert len(result["log_lines"]) <= 3


def test_extract_includes_max_rounds_when_provided():
    result = _extract_live_status(["[pipeline] round=5 done"], max_rounds=200)
    assert result["max_rounds"] == 200


def test_extract_no_max_rounds_when_not_provided():
    result = _extract_live_status(["[pipeline] round=5 done"])
    assert "max_rounds" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_live_status_extraction.py -k "extract" -v 2>&1 | head -30
```

Expected: FAIL — `ImportError: cannot import name '_extract_live_status'`

- [ ] **Step 3: Add `_extract_live_status` to `job_runner.py`**

In `saas/workers/job_runner.py`, add after the existing `import re` at the top (add `import re` if not present) and after the `_infer_pipeline_stage` function:

```python
import re

_LOG_NOISE_RE = re.compile(r'(GET /|POST /|HEAD /|OPTIONS /)')

def _extract_live_status(log_lines: list[str], max_rounds: int | None = None) -> dict:
    """Extract round count and cleaned log lines from pod pipeline log output.

    Returns a dict suitable for storing in the live_status JSONB column.
    Keys present: log_lines (always), round (if found), max_rounds (if provided).
    """
    cleaned = [
        line for line in log_lines
        if line.strip()
        and not _LOG_NOISE_RE.search(line)
        and len(line.strip()) >= 10
    ][-3:]

    round_num: int | None = None
    for line in log_lines:
        m = re.search(r'round[=\s]+(\d+)', line, re.IGNORECASE)
        if m:
            candidate = int(m.group(1))
            if round_num is None or candidate > round_num:
                round_num = candidate

    result: dict = {"log_lines": cleaned}
    if round_num is not None:
        result["round"] = round_num
    if max_rounds is not None:
        result["max_rounds"] = max_rounds
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_live_status_extraction.py -k "extract" -v
```

Expected: all extraction tests PASS

- [ ] **Step 5: Commit**

```bash
git add saas/workers/job_runner.py tests/test_live_status_extraction.py
git commit -m "feat: add _extract_live_status helper with unit tests"
```

---

## Task 3: Persistence Helper

**Files:**
- Modify: `saas/workers/persistence.py`
- Modify: `saas/workers/tasks.py` (import)

- [ ] **Step 1: Add `_update_live_status_sync` to `persistence.py`**

In `saas/workers/persistence.py`, add after `_update_heartbeat_sync`:

```python
def _update_live_status_sync(job_id: int, live_status: dict) -> None:
    """Write live_status JSONB for a running job (sync, for Celery).

    Uses _get_sync_engine() / psycopg2 — never the shared async pool.
    Silently skips if DATABASE_URL is unset (e.g. tests without DB).
    """
    import json
    from sqlalchemy import text

    engine = _get_sync_engine()
    if engine is None:
        logger.warning("DATABASE_URL not set; skipping live_status update for job %d", job_id)
        return
    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    "UPDATE simulation_jobs "
                    "SET live_status = CAST(:live_status AS JSONB) "
                    "WHERE id = :job_id"
                ),
                {"live_status": json.dumps(live_status), "job_id": job_id},
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Could not update live_status for job %d: %s", job_id, exc)
    finally:
        engine.dispose()
```

- [ ] **Step 2: Add import in `tasks.py`**

In `saas/workers/tasks.py`, add `_update_live_status_sync` to the persistence imports:

```python
from saas.workers.persistence import (
    _update_pipeline_stage_sync,
    _update_heartbeat_sync,
    _update_pod_id,
    _extract_key_insight,
    _get_job_status,
    _mark_job_failed,
    _save_job_results,
    _update_enrichment,
    _update_job_metadata,
    _update_job_retry,
    _update_sim_data_available,
    _update_live_status_sync,
)
```

- [ ] **Step 3: Verify backend tests still pass**

```bash
pytest tests/ -x -q
```

Expected: all existing tests PASS

- [ ] **Step 4: Commit**

```bash
git add saas/workers/persistence.py saas/workers/tasks.py
git commit -m "feat: add _update_live_status_sync persistence helper"
```

---

## Task 4: Pod `/partial_chat` Endpoint

**Files:**
- Modify: `infra/docker/worker_api.py`

- [ ] **Step 1: Add the endpoint**

In `infra/docker/worker_api.py`, add after the `logs` route (before `if __name__ == "__main__":`):

```python
@app.route("/partial_chat", methods=["GET"])
def partial_chat():
    """Return the last N chat messages from the in-progress pipeline.

    Reads /tmp/results/chat_log.json which run_job.py writes incrementally.
    Returns [] gracefully if the file doesn't exist or is mid-write (partial JSON).
    """
    tail = request.args.get("tail", 20, type=int)
    path = Path("/tmp/results/chat_log.json")
    if not path.exists():
        return jsonify({"messages": []})
    try:
        data = json.loads(path.read_text())
        messages = data[-tail:] if isinstance(data, list) else []
    except Exception:
        messages = []
    return jsonify({"messages": messages})
```

Note: `json` is already imported at the top of `worker_api.py` (it's not — add `import json` at the top if missing). `Path` is imported from `pathlib`.

Check the existing imports at the top of `worker_api.py`. If `import json` is missing, add it. `Path` is already imported.

- [ ] **Step 2: Verify `import json` exists**

Read the top of `worker_api.py`. If `import json` is not present, add it after `import threading`.

- [ ] **Step 3: Rebuild and push worker image**

```bash
# From repo root
docker build -f infra/docker/Dockerfile -t ghcr.io/sneg55/simswarm-worker:v$(date +%Y%m%d%H%M%S) infra/docker/
docker push ghcr.io/sneg55/simswarm-worker:<new-tag>
```

Then update `WORKER_IMAGE_DEFAULT_TAG` in `saas/workers/job_runner.py` to the new tag.

- [ ] **Step 4: Commit**

```bash
git add infra/docker/worker_api.py saas/workers/job_runner.py
git commit -m "feat: add /partial_chat endpoint to GPU worker pod"
```

---

## Task 5: Worker Polling Uplift

**Files:**
- Modify: `saas/workers/job_runner.py`

The `_poll_until_complete` method currently fetches logs every 6 polls (60s). This task changes it to every 2 polls (~20s), extracts live status, fetches partial chat when simulating, and writes to DB.

- [ ] **Step 1: Add imports at top of `job_runner.py`**

`job_runner.py` currently does not import from `persistence`. Add after the existing imports:

```python
from saas.workers.persistence import _update_live_status_sync
```

- [ ] **Step 2: Replace the log-fetching block in `_poll_until_complete`**

Find this block in `_poll_until_complete` (around line 330):

```python
                if poll % 6 == 0:  # Log every 60s
                    elapsed = int(time.monotonic() - poll_start)
                    logger.info(f"Pipeline status: {job_status} ({elapsed}s elapsed, poll {poll + 1}/{max_polls})")
                    # Pull recent logs from the worker
                    try:
                        log_resp = await http.get(f"{worker_url}/logs?tail=10", timeout=10)
                        if log_resp.status_code == 200:
                            log_data = log_resp.json()
                            log_lines = log_data.get("lines", [])
                            for line in log_lines:
                                logger.info(f"  [worker] {line}")
                    except Exception:
                        pass

                # Infer pipeline stage from logs and notify callback if changed
                stage = _infer_pipeline_stage(log_lines)
                if stage is not None and stage != last_stage:
                    last_stage = stage
                    logger.info(f"Pipeline stage updated to {stage}")
                    if self._stage_callback is not None:
                        try:
                            await self._stage_callback(config.job_id, stage)
                        except Exception as cb_exc:
                            logger.warning(f"Stage callback failed: {cb_exc}")
```

Replace with:

```python
                if poll % 2 == 0:  # Poll logs every ~20s
                    elapsed = int(time.monotonic() - poll_start)
                    logger.info(f"Pipeline status: {job_status} ({elapsed}s elapsed, poll {poll + 1}/{max_polls})")
                    # Pull recent pipeline logs
                    log_lines = []
                    try:
                        log_resp = await http.get(f"{worker_url}/logs?tail=20&source=pipeline", timeout=10)
                        if log_resp.status_code == 200:
                            log_data = log_resp.json()
                            log_lines = log_data.get("lines", [])
                            for line in log_lines[-5:]:
                                logger.info(f"  [worker] {line}")
                    except Exception:
                        pass

                    # Infer pipeline stage from logs and notify callback if changed
                    stage = _infer_pipeline_stage(log_lines)
                    if stage is not None and stage != last_stage:
                        last_stage = stage
                        logger.info(f"Pipeline stage updated to {stage}")
                        if self._stage_callback is not None:
                            try:
                                await self._stage_callback(config.job_id, stage)
                            except Exception as cb_exc:
                                logger.warning(f"Stage callback failed: {cb_exc}")

                    # Build live_status from log data
                    max_rounds = getattr(config, "max_rounds", None)
                    live = _extract_live_status(log_lines, max_rounds=max_rounds)

                    # Fetch partial chat when simulation stage is active
                    if (last_stage or 0) >= 3:
                        try:
                            chat_resp = await http.get(
                                f"{worker_url}/partial_chat?tail=10", timeout=10
                            )
                            if chat_resp.status_code == 200:
                                live["partial_chat"] = chat_resp.json().get("messages", [])
                        except Exception:
                            live["partial_chat"] = []

                    live["updated_at"] = time.time()  # time is imported at the top of this method

                    # Write to DB only when something has changed
                    new_round = live.get("round")
                    new_log_lines = live.get("log_lines", [])
                    new_chat_count = len(live.get("partial_chat", []))
                    if (
                        new_round != _last_round
                        or new_log_lines != _last_log_lines
                        or new_chat_count != _last_chat_count
                    ):
                        _last_round = new_round
                        _last_log_lines = new_log_lines
                        _last_chat_count = new_chat_count
                        try:
                            _update_live_status_sync(config.job_id, live)
                        except Exception as exc:
                            logger.warning("live_status write failed for job %d: %s", config.job_id, exc)
```

- [ ] **Step 3: Initialize tracking variables before the polling loop**

Find the line `last_stage: int | None = None` in `_poll_until_complete` and add the three tracking variables immediately after:

```python
            last_stage: int | None = None
            last_heartbeat_time = 0.0
            _last_round: int | None = None
            _last_log_lines: list[str] = []
            _last_chat_count: int = 0
```

- [ ] **Step 4: Remove the now-orphaned `log_lines` initialisation**

The old code had `log_lines: list[str] = []` before the `if poll % 6 == 0` block. Find it and remove it (it's now initialised inside the `if poll % 2 == 0` block). Search for `log_lines: list[str] = []` in the method and delete that line.

- [ ] **Step 5: Run backend tests**

```bash
pytest tests/ -x -q
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add saas/workers/job_runner.py
git commit -m "feat: uplift worker log polling to 20s, write live_status to DB"
```

---

## Task 6: LiveActivity.vue Component

**Files:**
- Create: `frontend/src/components/LiveActivity.vue`
- Create: `frontend/src/components/__tests__/LiveActivity.test.js`

- [ ] **Step 1: Write failing Vitest tests**

Create `frontend/src/components/__tests__/LiveActivity.test.js`:

```js
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import LiveActivity from '../LiveActivity.vue'

describe('LiveActivity', () => {
  it('is collapsed by default when prop open not provided — starts open', () => {
    const wrapper = mount(LiveActivity, {
      props: { logLines: ['[pipeline] Building graph here'], partialChat: [], stage: 1 },
    })
    // Default is open=true; log line text should be visible
    expect(wrapper.text()).toContain('Building graph here')
  })

  it('renders log lines when partialChat is empty', () => {
    const wrapper = mount(LiveActivity, {
      props: {
        logLines: ['[pipeline] 12 entities extracted', '[pipeline] Building knowledge graph'],
        partialChat: [],
        stage: 1,
      },
    })
    expect(wrapper.text()).toContain('12 entities extracted')
    expect(wrapper.text()).toContain('Building knowledge graph')
  })

  it('strips [pipeline] prefix from log lines', () => {
    const wrapper = mount(LiveActivity, {
      props: { logLines: ['[pipeline] 12 entities extracted'], partialChat: [], stage: 1 },
    })
    expect(wrapper.text()).not.toContain('[pipeline]')
    expect(wrapper.text()).toContain('12 entities extracted')
  })

  it('renders agent messages from partialChat', () => {
    const messages = [
      { agent: 'agent_47', content: 'First message content here', role: 'assistant' },
      { agent: 'agent_12', content: 'Latest message content', role: 'assistant' },
    ]
    const wrapper = mount(LiveActivity, {
      props: { logLines: [], partialChat: messages, stage: 3 },
    })
    expect(wrapper.text()).toContain('First message content here')
    expect(wrapper.text()).toContain('Latest message content')
  })

  it('shows LIVE badge only on the last message', () => {
    const messages = [
      { agent: 'agent_1', content: 'first message text', role: 'assistant' },
      { agent: 'agent_2', content: 'second message text', role: 'assistant' },
    ]
    const wrapper = mount(LiveActivity, {
      props: { logLines: [], partialChat: messages, stage: 3 },
    })
    const liveBadges = wrapper.findAll('[data-testid="live-badge"]')
    expect(liveBadges).toHaveLength(1)
  })

  it('hides log lines section when partialChat has messages', () => {
    const wrapper = mount(LiveActivity, {
      props: {
        logLines: ['[pipeline] some log line here'],
        partialChat: [{ agent: 'a', content: 'msg', role: 'assistant' }],
        stage: 3,
      },
    })
    expect(wrapper.find('[data-testid="log-lines"]').exists()).toBe(false)
  })

  it('collapses when header is clicked', async () => {
    const wrapper = mount(LiveActivity, {
      props: { logLines: ['[pipeline] 12 entities extracted'], partialChat: [], stage: 1 },
    })
    expect(wrapper.text()).toContain('12 entities extracted')
    await wrapper.find('button').trigger('click')
    // After collapse, the body div is hidden (v-show)
    const body = wrapper.find('[data-testid="live-body"]')
    expect(body.isVisible()).toBe(false)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npm test -- --reporter=verbose LiveActivity 2>&1 | head -40
```

Expected: FAIL — `Cannot find module '../LiveActivity.vue'`

- [ ] **Step 3: Create `LiveActivity.vue`**

Create `frontend/src/components/LiveActivity.vue`:

```vue
<template>
  <div class="bg-ocean-deep border border-mist-depth rounded-2xl overflow-hidden">
    <button
      @click="open = !open"
      class="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-ocean-teal/5 transition-colors"
    >
      <span class="text-sm font-semibold text-ocean-glow flex items-center gap-2">
        <span class="w-1.5 h-1.5 rounded-full bg-organic-violet animate-[breathe_2.5s_ease-in-out_infinite]" />
        Live Activity
      </span>
      <svg
        class="w-4 h-4 text-mist-slate transition-transform"
        :class="{ 'rotate-180': open }"
        fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"
      >
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>

    <div v-show="open" data-testid="live-body" class="px-5 pb-4">
      <!-- Log lines: shown when no chat messages yet -->
      <div
        v-if="logLines.length > 0 && partialChat.length === 0"
        data-testid="log-lines"
        class="space-y-1 pt-2"
      >
        <div
          v-for="(line, i) in logLines"
          :key="i"
          class="font-mono text-xs text-mist-drift flex items-start gap-2"
        >
          <span class="text-mist-depth mt-0.5 select-none">·</span>
          <span>{{ stripPrefix(line) }}</span>
        </div>
      </div>

      <!-- Agent feed: shown when partial chat messages are available -->
      <div
        v-if="partialChat.length > 0"
        class="space-y-2 pt-2 max-h-[300px] overflow-y-auto"
        style="scrollbar-width: thin; scrollbar-color: #164E63 #0B1426;"
      >
        <div
          v-for="(msg, idx) in partialChat"
          :key="idx"
          class="max-w-[85%] px-3.5 py-2.5 rounded-xl text-sm bg-ocean-abyss border border-mist-depth text-mist"
        >
          <div
            class="text-[11px] font-semibold mb-1 flex items-center gap-1.5"
            :style="{ color: agentColor(msg.agent || msg.agent_id) }"
          >
            {{ msg.agent || msg.agent_id || 'Agent' }}
            <span
              v-if="idx === partialChat.length - 1"
              data-testid="live-badge"
              class="flex items-center gap-1 text-ocean-glow font-normal text-[10px]"
            >
              <span class="w-1 h-1 rounded-full bg-ocean-glow animate-[breathe_2.5s_ease-in-out_infinite]" />
              LIVE
            </span>
          </div>
          <div class="whitespace-pre-wrap">{{ msg.content }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  logLines: { type: Array, default: () => [] },
  partialChat: { type: Array, default: () => [] },
  stage: { type: Number, default: 0 },
})

const open = ref(true)

function stripPrefix(line) {
  return line.replace(/^\[(pipeline|vllm)\]\s*/, '')
}

function agentColor(agent) {
  if (!agent) return '#94A3B8'
  const palette = ['#22D3EE', '#A78BFA', '#6EE7B7', '#FF6B6B', '#FBBF24', '#F97316']
  let hash = 0
  for (let i = 0; i < agent.length; i++) hash = ((hash << 5) - hash + agent.charCodeAt(i)) | 0
  return palette[Math.abs(hash) % palette.length]
}
</script>
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npm test -- --reporter=verbose LiveActivity
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/LiveActivity.vue frontend/src/components/__tests__/LiveActivity.test.js
git commit -m "feat: add LiveActivity component with live agent feed and log lines"
```

---

## Task 7: SimulationStatus.vue Updates

**Files:**
- Modify: `frontend/src/views/SimulationStatus.vue`

- [ ] **Step 1: Add import**

In `SimulationStatus.vue`, add `LiveActivity` to the imports block (inside `<script setup>`):

```js
import LiveActivity from '../components/LiveActivity.vue'
```

- [ ] **Step 2: Add computed properties for live_status data**

Add these computed properties after the existing `chatMessages` computed (around line 305):

```js
const liveStatus = computed(() => job.value?.live_status || null)
const liveLogLines = computed(() => liveStatus.value?.log_lines || [])
const livePartialChat = computed(() => liveStatus.value?.partial_chat || [])
const liveRound = computed(() => liveStatus.value?.round ?? null)
const liveMaxRounds = computed(() => liveStatus.value?.max_rounds ?? null)
const isLiveStale = computed(() => {
  if (!liveStatus.value?.updated_at) return true
  return (Date.now() / 1000 - liveStatus.value.updated_at) > 120
})
const showLiveActivity = computed(() =>
  isActive.value &&
  !isLiveStale.value &&
  (liveLogLines.value.length > 0 || livePartialChat.value.length > 0)
)
```

- [ ] **Step 3: Add Rounds row to the progress card**

In the template, find the `Estimated remaining` row inside the `<template v-if="isActive">` block:

```html
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Estimated remaining</span>
              <span class="font-mono text-sm text-ocean-glow tabular-nums">{{ eta }}</span>
            </div>
```

Add the Rounds row immediately after it:

```html
            <div class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Estimated remaining</span>
              <span class="font-mono text-sm text-ocean-glow tabular-nums">{{ eta }}</span>
            </div>
            <div v-if="liveRound !== null && job.pipeline_stage === 3 && !isLiveStale"
              class="flex items-center justify-between">
              <span class="text-sm text-mist-drift">Rounds</span>
              <span class="font-mono text-sm text-mist-foam tabular-nums">
                {{ liveRound }} <span class="text-mist-slate font-normal">/ {{ liveMaxRounds || '--' }}</span>
              </span>
            </div>
```

- [ ] **Step 4: Add LiveActivity component below the progress card**

Find the email notification banner in the template:

```html
      <!-- Email notification banner -->
      <div v-if="isActive || job.status === 'PENDING'" class="flex items-center gap-3 ...">
```

Add the `LiveActivity` component immediately before that banner:

```html
      <!-- Live Activity feed (log lines + partial chat during run) -->
      <LiveActivity
        v-if="showLiveActivity"
        :log-lines="liveLogLines"
        :partial-chat="livePartialChat"
        :stage="job.pipeline_stage || 0"
      />

      <!-- Email notification banner -->
      <div v-if="isActive || job.status === 'PENDING'" class="flex items-center gap-3 ...">
```

- [ ] **Step 5: Run frontend tests**

```bash
cd frontend && npm test
```

Expected: all tests PASS (no regressions)

- [ ] **Step 6: Run full backend test suite**

```bash
pytest tests/ -q
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/SimulationStatus.vue
git commit -m "feat: surface round count and live agent feed on simulation status page"
```

---

## Spec Coverage Check

| Spec Requirement | Covered By |
|-----------------|------------|
| `live_status` JSONB column | Task 1 |
| Alembic migration | Task 1 |
| `JobResponse` includes `live_status` | Task 1 |
| `_extract_live_status` helper with noise filtering | Task 2 |
| Round regex extraction | Task 2 |
| `_update_live_status_sync` via psycopg2 | Task 3 |
| Pod `/partial_chat` endpoint | Task 4 |
| Poll every 2 cycles (~20s) | Task 5 |
| Partial chat only when stage ≥ 3 | Task 5 |
| Skip DB write when nothing changed | Task 5 |
| Rounds row (stage=3 only, not stale) | Task 7 |
| `LiveActivity.vue` collapsible | Task 6 |
| Log lines section | Task 6 |
| Agent feed section | Task 6 |
| LIVE badge on latest message only | Task 6 |
| Stale detection (>120s) hides UI | Task 7 (isLiveStale) |
| LiveActivity above email banner | Task 7 |
| Graceful degradation (null live_status) | Task 6 (v-if), Task 7 (showLiveActivity) |
