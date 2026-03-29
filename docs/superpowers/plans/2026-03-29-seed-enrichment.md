# Seed Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich thin seed texts with web + X/Twitter research via xAI's Responses API before the simulation pipeline runs, improving ontology and report quality with zero added latency.

**Architecture:** The Celery worker calls xAI's grok model with web_search + x_search tools before dispatching to the GPU pod. The enriched text is appended to the original seed as a "Background Research" section, persisted on the job row, and displayed to the user during the simulation wait and in results.

**Tech Stack:** Python (openai SDK with xAI base_url), FastAPI, SQLAlchemy, Alembic, Vue 3, Tailwind CSS

---

## Task 1: Add enrichment columns to SimulationJob model + migration

**Files:**
- Modify: `saas/models/job.py`
- Create: `alembic/versions/j1k2l3m4n5o6_add_enrichment_columns.py`

- [ ] **Step 1: Add columns to SimulationJob model**

In `saas/models/job.py`, add after the `last_heartbeat` column (line 50):

```python
    enrich_web: Mapped[bool] = mapped_column(default=True)
    enriched_seed: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_citations: Mapped[str | None] = mapped_column(Text, nullable=True)
```

- [ ] **Step 2: Create Alembic migration**

Create `alembic/versions/j1k2l3m4n5o6_add_enrichment_columns.py`:

```python
"""add enrichment columns to simulation_jobs

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "j1k2l3m4n5o6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("simulation_jobs", sa.Column("enrich_web", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("simulation_jobs", sa.Column("enriched_seed", sa.Text(), nullable=True))
    op.add_column("simulation_jobs", sa.Column("enrichment_citations", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("simulation_jobs", "enrichment_citations")
    op.drop_column("simulation_jobs", "enriched_seed")
    op.drop_column("simulation_jobs", "enrich_web")
```

Check what the latest revision ID actually is — read the latest migration file in `alembic/versions/` and use that as `down_revision`.

- [ ] **Step 3: Run tests**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat && python -m pytest tests/ -x -q`
Expected: All pass (SQLite test DB picks up new columns via create_all)

- [ ] **Step 4: Commit**

```bash
git add saas/models/job.py alembic/versions/j1k2l3m4n5o6_add_enrichment_columns.py
git commit -m "feat: add enrichment columns to SimulationJob model (#43)"
```

---

## Task 2: Update schemas and job creation to support enrich_web toggle

**Files:**
- Modify: `saas/schemas/jobs.py`
- Modify: `saas/api/jobs.py`
- Modify: `saas/config.py`

- [ ] **Step 1: Add enrich_web to JobCreate and enrichment fields to JobResponse/JobSummary**

In `saas/schemas/jobs.py`:

Add to `JobCreate`:
```python
class JobCreate(BaseModel):
    seed_text: str
    goal: str
    tier: TierEnum
    enrich_web: bool = True
```

Add to `JobResponse` (after `result_structured`):
```python
    enriched_seed: str | None = None
    enrichment_citations: str | None = None
    enrich_web: bool = True
```

Add to `JobSummary` (after `error_message`):
```python
    enrich_web: bool = True
    enriched_seed: str | None = None
```

- [ ] **Step 2: Pass enrich_web through job creation**

In `saas/api/jobs.py`, update the `create_job` function. When creating the SimulationJob:

```python
    job = SimulationJob(
        user_id=user_id,
        seed_text=body.seed_text,
        goal=body.goal,
        tier=body.tier.value,
        credits_charged=credits,
        status=JobStatus.PENDING,
        enrich_web=body.enrich_web,
    )
```

Also pass `enrich_web` to the Celery task — add it as a parameter to `run_simulation_task.delay(...)`:

```python
        task_result = run_simulation_task.delay(
            ...existing params...,
            enrich_web=body.enrich_web,
        )
```

- [ ] **Step 3: Add XAI_API_KEY to Settings**

In `saas/config.py`, add:

```python
    # xAI enrichment
    XAI_API_KEY: str = ""
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat && python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add saas/schemas/jobs.py saas/api/jobs.py saas/config.py
git commit -m "feat: add enrich_web toggle to job creation schema (#43)"
```

---

## Task 3: Core enrichment module

**Files:**
- Create: `saas/workers/enrichment.py`
- Create: `tests/test_enrichment.py`

- [ ] **Step 1: Write tests for enrichment logic**

Create `tests/test_enrichment.py`:

```python
"""Tests for seed enrichment via xAI search."""
import pytest
from unittest.mock import patch, MagicMock


def test_enrich_seed_returns_none_when_no_api_key(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "")
    from saas.workers.enrichment import enrich_seed
    result = enrich_seed("some seed", "some goal")
    assert result is None


def test_enrich_seed_returns_none_on_api_error(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    with patch("saas.workers.enrichment.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.responses.create.side_effect = Exception("API error")
        from saas.workers.enrichment import enrich_seed
        result = enrich_seed("some seed", "some goal")
        assert result is None


def test_enrich_seed_returns_result_on_success(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    with patch("saas.workers.enrichment.OpenAI") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.output_text = "Research summary about the topic."
        mock_response.citations = [
            MagicMock(url="https://example.com/1", title="Source 1"),
            MagicMock(url="https://example.com/2", title="Source 2"),
        ]
        mock_client.responses.create.return_value = mock_response

        from saas.workers.enrichment import enrich_seed
        result = enrich_seed("seed text", "research goal")

        assert result is not None
        assert result.summary == "Research summary about the topic."
        assert len(result.citations) == 2
        assert result.citations[0]["url"] == "https://example.com/1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat && python -m pytest tests/test_enrichment.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Create enrichment module**

Create `saas/workers/enrichment.py`:

```python
"""Seed text enrichment via xAI web + X search."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EnrichmentResult:
    summary: str
    citations: list[dict]  # [{url, title}, ...]


def enrich_seed(seed_text: str, goal: str) -> EnrichmentResult | None:
    """Call xAI Responses API with web_search + x_search to research the seed topic.

    Returns EnrichmentResult on success, None on failure or missing API key.
    """
    api_key = os.getenv("XAI_API_KEY", "")
    if not api_key:
        logger.debug("XAI_API_KEY not set — skipping enrichment")
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

        prompt = (
            "You are a research assistant preparing background material for a social media simulation.\n\n"
            f"SIMULATION GOAL: {goal}\n\n"
            f"SEED MATERIAL:\n{seed_text[:5000]}\n\n"
            "Research this topic thoroughly. Provide:\n"
            "1. Background context and key facts\n"
            "2. Key entities involved (people, organizations, policies) and their roles\n"
            "3. Recent developments and timeline\n"
            "4. Relevant social media discourse and public sentiment\n"
            "5. Any controversies or opposing viewpoints\n\n"
            "Be factual and cite your sources. Write 300-500 words."
        )

        response = client.responses.create(
            model="grok-3-mini",
            tools=[{"type": "web_search"}, {"type": "x_search"}],
            input=prompt,
            timeout=30,
        )

        summary = response.output_text or ""
        if not summary.strip():
            logger.warning("enrichment returned empty summary")
            return None

        citations = []
        for c in getattr(response, "citations", []) or []:
            url = getattr(c, "url", None) or (c.get("url") if isinstance(c, dict) else None)
            title = getattr(c, "title", None) or (c.get("title", "") if isinstance(c, dict) else "")
            if url:
                citations.append({"url": url, "title": title or ""})

        logger.info("enrichment.success goal=%s summary_len=%d citations=%d", goal[:50], len(summary), len(citations))
        return EnrichmentResult(summary=summary, citations=citations)

    except Exception as exc:
        logger.warning("enrichment.failed error=%s", exc)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat && python -m pytest tests/test_enrichment.py -v`
Expected: All 3 pass

- [ ] **Step 5: Run full test suite**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat && python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add saas/workers/enrichment.py tests/test_enrichment.py
git commit -m "feat: core seed enrichment module with xAI web+X search (#43)"
```

---

## Task 4: Wire enrichment into Celery task + persistence

**Files:**
- Modify: `saas/workers/tasks.py`
- Modify: `saas/workers/persistence.py`

- [ ] **Step 1: Add enrichment persistence helper**

In `saas/workers/persistence.py`, add a new function (after the existing helpers):

```python
def _update_enrichment(job_id: int, enriched_text: str, citations_json: str) -> None:
    """Persist enrichment results to the SimulationJob row."""
    from sqlalchemy import text

    factory = _get_worker_session_factory()
    if factory is None:
        return

    async def _do_update():
        async with factory() as session:
            try:
                await session.execute(
                    text(
                        "UPDATE simulation_jobs "
                        "SET enriched_seed = :enriched, enrichment_citations = :citations "
                        "WHERE id = :job_id"
                    ),
                    {"enriched": enriched_text, "citations": citations_json, "job_id": job_id},
                )
                await session.commit()
                logger.info("Saved enrichment for job %d (%d chars)", job_id, len(enriched_text))
            except Exception as exc:
                logger.warning("Could not save enrichment for job %d: %s", job_id, exc)

    _run_async(_do_update())
```

- [ ] **Step 2: Wire enrichment into run_simulation_task**

In `saas/workers/tasks.py`, update `run_simulation_task`:

Add `enrich_web: bool = True` parameter to the function signature (after `credits_charged`).

Before `config = JobConfig(...)`, add enrichment logic:

```python
    # Enrich seed text if enabled
    enriched_seed_text = seed_text
    if enrich_web:
        from saas.workers.enrichment import enrich_seed
        enrichment = enrich_seed(seed_text, goal)
        if enrichment:
            import json as _json
            _update_enrichment(job_id, enrichment.summary, _json.dumps(enrichment.citations))
            enriched_seed_text = seed_text + "\n\n--- Background Research ---\n" + enrichment.summary

    config = JobConfig(
        job_id=job_id,
        user_id=user_id,
        seed_text=enriched_seed_text,  # Use enriched version
        ...rest unchanged...
    )
```

Add `_update_enrichment` to the imports from persistence.

- [ ] **Step 3: Run tests**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat && python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add saas/workers/tasks.py saas/workers/persistence.py
git commit -m "feat: wire enrichment into Celery task with persistence (#43)"
```

---

## Task 5: Enrichment retry endpoint

**Files:**
- Modify: `saas/api/jobs.py`
- Modify: `saas/workers/tasks.py`

- [ ] **Step 1: Add enrich-retry Celery task**

In `saas/workers/tasks.py`, add a new lightweight task:

```python
@celery_app.task(name="fishcloud.enrich_retry")
def enrich_retry_task(job_id: int, seed_text: str, goal: str) -> dict:
    """Retry enrichment for a job that failed enrichment initially."""
    from saas.workers.enrichment import enrich_seed
    import json as _json

    enrichment = enrich_seed(seed_text, goal)
    if enrichment:
        _update_enrichment(job_id, enrichment.summary, _json.dumps(enrichment.citations))
        return {"status": "enriched", "summary_length": len(enrichment.summary)}
    return {"status": "failed"}
```

- [ ] **Step 2: Add POST /jobs/{id}/enrich-retry endpoint**

In `saas/api/jobs.py`, add:

```python
@router.post("/{job_id}/enrich-retry", status_code=202)
async def retry_enrichment(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Re-run seed enrichment for a job that failed enrichment."""
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    from saas.workers.tasks import enrich_retry_task
    enrich_retry_task.delay(job_id=job.id, seed_text=job.seed_text, goal=job.goal)
    return {"status": "retrying"}
```

- [ ] **Step 3: Run tests**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat && python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add saas/api/jobs.py saas/workers/tasks.py
git commit -m "feat: enrichment retry endpoint POST /jobs/{id}/enrich-retry (#43)"
```

---

## Task 6: Frontend — enrichment toggle in NewSimulation

**Files:**
- Modify: `frontend/src/views/NewSimulation.vue`
- Modify: `frontend/src/api/jobs.js`

- [ ] **Step 1: Add enrich_web to createJob API call**

In `frontend/src/api/jobs.js`, update `createJob`:

```javascript
export async function createJob(payload) {
  const body = {
    seed_text: payload.seed_text,
    goal: payload.goal,
    tier: payload.tier,
    enrich_web: payload.enrich_web ?? true,
  }
  const response = await api.post('/jobs', body)
  return response.data
}
```

- [ ] **Step 2: Add toggle checkbox to NewSimulation.vue**

Read `frontend/src/views/NewSimulation.vue` to find where to add the toggle. Add an `enrichWeb` ref and a checkbox. The checkbox should go in the launch step (step 3, WizardLaunch area), before the submit button:

Add ref:
```javascript
const enrichWeb = ref(true)
```

Add checkbox in the step 3 template (before or after the tier selector):
```html
<label class="flex items-center gap-3 mt-4 cursor-pointer group">
  <input
    type="checkbox"
    v-model="enrichWeb"
    class="w-4 h-4 rounded border-mist-depth bg-ocean-abyss text-ocean-cyan focus:ring-ocean-cyan/30"
  >
  <span class="text-sm text-mist-drift group-hover:text-mist-foam transition-colors">
    Enrich with web research
  </span>
</label>
```

Update the `createJob` call to pass `enrich_web: enrichWeb.value`.

- [ ] **Step 3: Add retryEnrichment to jobs API**

In `frontend/src/api/jobs.js`, add:

```javascript
export async function retryEnrichment(jobId) {
  const response = await api.post(`/jobs/${jobId}/enrich-retry`)
  return response.data
}
```

- [ ] **Step 4: Run frontend tests**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat/frontend && npm test -- --run`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/NewSimulation.vue frontend/src/api/jobs.js
git commit -m "feat: enrichment toggle in NewSimulation + retryEnrichment API (#43)"
```

---

## Task 7: Frontend — enrichment display in SimulationStatus + Results

**Files:**
- Modify: `frontend/src/views/SimulationStatus.vue`
- Modify: `frontend/src/views/SimulationResults.vue`

- [ ] **Step 1: Add research card to SimulationStatus.vue**

Read `frontend/src/views/SimulationStatus.vue`. Add a collapsible "Web Research" card below the pipeline progress section.

When `job.enriched_seed` exists, show:
```html
<!-- Web Research -->
<div v-if="job.enriched_seed" class="bg-ocean-deep border border-mist-depth rounded-2xl overflow-hidden">
  <button
    @click="researchOpen = !researchOpen"
    class="w-full flex items-center justify-between px-5 py-3 text-left hover:bg-ocean-teal/5 transition-colors"
  >
    <span class="text-sm font-semibold text-ocean-glow flex items-center gap-2">
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
      Web Research
    </span>
    <svg class="w-4 h-4 text-mist-slate transition-transform" :class="{ 'rotate-180': researchOpen }" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><polyline points="6 9 12 15 18 9"/></svg>
  </button>
  <div v-show="researchOpen" class="px-5 pb-4 text-sm text-mist-drift leading-relaxed whitespace-pre-line">
    {{ job.enriched_seed }}
    <div v-if="citations.length" class="mt-3 pt-3 border-t border-mist-depth/30 space-y-1">
      <a v-for="(c, i) in citations" :key="i" :href="c.url" target="_blank" rel="noopener"
         class="block text-xs text-ocean-glow/70 hover:text-ocean-glow truncate">
        {{ c.title || c.url }}
      </a>
    </div>
  </div>
</div>
```

When enrichment failed (enrich_web true, enriched_seed null, job still active):
```html
<div v-else-if="job.enrich_web && !job.enriched_seed && isActive" class="flex items-center gap-3 px-5 py-3 rounded-xl bg-organic-violet/5 border border-organic-violet/15 text-sm text-mist-drift">
  Web research unavailable — running with your original seed
  <button @click="retryEnrich" :disabled="enrichRetrying" class="text-ocean-glow hover:underline text-xs ml-auto">
    {{ enrichRetrying ? 'Retrying...' : 'Retry' }}
  </button>
</div>
```

Add refs and logic:
```javascript
import { retryEnrichment } from '../api/jobs.js'

const researchOpen = ref(false)
const enrichRetrying = ref(false)

const citations = computed(() => {
  if (!job.value?.enrichment_citations) return []
  try { return JSON.parse(job.value.enrichment_citations) } catch { return [] }
})

async function retryEnrich() {
  enrichRetrying.value = true
  try {
    await retryEnrichment(jobId)
  } catch { /* ignore */ }
  enrichRetrying.value = false
}
```

- [ ] **Step 2: Add Sources section to SimulationResults.vue**

Read `frontend/src/views/SimulationResults.vue`. In the Story view, add a "Sources & Background" section at the bottom (after the report card):

```html
<!-- Sources & Background (from enrichment) -->
<div v-if="job.enriched_seed" id="story-sources" data-reveal class="bg-ocean-deep border border-mist-depth rounded-2xl p-8">
  <h2 class="text-lg font-bold text-mist-foam mb-4">Sources & Background</h2>
  <p class="text-sm text-mist-drift leading-relaxed whitespace-pre-line">{{ job.enriched_seed }}</p>
  <div v-if="enrichmentCitations.length" class="mt-4 pt-4 border-t border-mist-depth/30 space-y-1.5">
    <a v-for="(c, i) in enrichmentCitations" :key="i" :href="c.url" target="_blank" rel="noopener"
       class="flex items-center gap-2 text-sm text-ocean-glow/70 hover:text-ocean-glow transition-colors">
      <svg class="w-3 h-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
      {{ c.title || c.url }}
    </a>
  </div>
</div>
```

Add computed:
```javascript
const enrichmentCitations = computed(() => {
  if (!job.value?.enrichment_citations) return []
  try { return JSON.parse(job.value.enrichment_citations) } catch { return [] }
})
```

Also add "Sources" to `storySections` when enrichment exists:
```javascript
const storySections = computed(() => {
  const sections = [
    { id: 'story-header', label: 'Overview' },
    { id: 'story-report', label: 'Report' },
  ]
  if (job.value?.enriched_seed) sections.push({ id: 'story-sources', label: 'Sources' })
  return sections
})
```

- [ ] **Step 3: Run frontend tests**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat/frontend && npm test -- --run`
Expected: All pass

- [ ] **Step 4: Run backend tests**

Run: `cd /Users/sneg55/Documents/GitHub/fishandcat && python -m pytest tests/ -x -q`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/SimulationStatus.vue frontend/src/views/SimulationResults.vue
git commit -m "feat: enrichment display in status (collapsible + retry) and results (sources) (#43)"
```
