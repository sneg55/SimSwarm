# Seed Enrichment via xAI Search

## Problem

Seed text quality is the foundation of the entire MiroFish pipeline — ontology, agent profiles, simulation behavior, and report quality all depend on it. Users often provide thin seeds (500-1500 chars) that lack context about key entities, events, or background. This especially hurts small tier simulations.

## Solution

Add an `enrich_seed()` step that runs **during GPU warmup** using xAI's Responses API with both `web_search` and `x_search` tools. The enrichment runs in parallel with pod provisioning — zero added latency. The result is appended to the original seed as a separate section, persisted on the job row, and shown to the user during the wait and in final results.

## Architecture

```
User submits job (toggle: "Enrich with web research" on)
  |
Celery task starts
  |-- GPU provisioning begins (async)
  |-- enrich_seed() calls xAI Responses API
  |     Input: seed_text + goal
  |     Tools: web_search + x_search (both in one call)
  |     Output: research summary with citations
  |
Enrichment stored on job row
Frontend polls -> SimulationStatus shows research summary
  |
GPU ready -> POST /job with enriched seed
  |
Pipeline runs (build_graph uses original + research)
  |
Results page includes "Sources & Background" section
```

## Components

### Backend

#### `saas/workers/enrichment.py` (new)

Core enrichment logic:

- `enrich_seed(seed_text: str, goal: str) -> EnrichmentResult | None`
- Uses OpenAI SDK with `base_url="https://api.x.ai/v1"`, model `grok-4.20-reasoning`
- Single API call with both `{"type": "web_search"}` and `{"type": "x_search"}` tools
- System prompt instructs the model to research the topic for a social media simulation: provide background context, key entities and their roles, recent developments, and relevant social media discourse. Cite all sources.
- Returns `EnrichmentResult(summary: str, citations: list[dict])` with summary text and citation objects `{url, title}`
- Timeout: 30 seconds
- On any failure (API error, timeout, missing key): returns None, logs warning

#### `saas/workers/tasks.py` (modify)

- In `run_simulation_task()`, enrichment runs **before** dispatching to `JobRunner.run()`:
  - If `enrich_web` is True and `XAI_API_KEY` is set, call `enrich_seed()` synchronously
  - This happens while the Celery worker is preparing the job — GPU provisioning hasn't started yet
  - Enrichment typically completes in 5-15 seconds (single API call)
  - Store result via `_update_enrichment(job_id, summary, citations_json)`
  - Construct combined seed_text (original + research) and pass to `JobConfig`
  - The combined seed is what gets sent to the pod via POST /job
- GPU provisioning + vLLM warmup (2-5 min) happens AFTER enrichment completes, so the enrichment cost is masked by the longer GPU wait

#### `saas/workers/persistence.py` (modify)

New helper:
- `_update_enrichment(job_id: int, enriched_text: str, citations_json: str) -> None`
- Updates `enriched_seed` and `enrichment_citations` columns

#### `saas/models/job.py` (modify)

New columns:
- `enriched_seed: Mapped[str | None]` — Text, nullable. The research summary.
- `enrichment_citations: Mapped[str | None]` — Text, nullable. JSON array of `{url, title}`.
- `enrich_web: Mapped[bool]` — Boolean, default True. User's toggle preference.

#### `saas/schemas/jobs.py` (modify)

- Add `enrich_web: bool = True` to `JobCreate`
- Add `enriched_seed: str | None = None` and `enrichment_citations: str | None = None` to `JobResponse` and `JobSummary`

#### `saas/config.py` (modify)

New setting:
- `XAI_API_KEY: str = ""` — xAI API key for enrichment. Empty = enrichment disabled.

#### `saas/api/jobs.py` (modify)

New endpoint:
- `POST /api/jobs/{id}/enrich-retry` — re-runs enrichment for a job that failed enrichment
  - Fires a Celery task for enrichment only
  - Updates job row if successful
  - Does NOT cancel or restart the running simulation
  - If the pod hasn't received the job yet (still in health check), the enriched seed will be used when the job is submitted
  - If the pod already started the pipeline, enrichment is stored for display only

#### `infra/docker/run_job.py` (modify)

In `run_pipeline()`, the seed_text arrives already enriched from the Celery worker. The enrichment is appended as:

```
{original_seed_text}

--- Background Research ---
{enriched_seed_text}
```

This combined text feeds into `build_graph()` and `prepare_simulation()`. No changes needed to run_job.py itself — the Celery worker constructs the combined seed before sending it to the pod via POST /job.

#### Alembic migration (new)

Add `enriched_seed` (Text, nullable), `enrichment_citations` (Text, nullable), and `enrich_web` (Boolean, default True) columns to `simulation_jobs` table.

### Frontend

#### `frontend/src/views/NewSimulation.vue` (modify)

Add checkbox in the simulation setup form:
- Label: "Enrich with web research"
- Default: checked
- Bound to `enrich_web` field, passed in job creation payload
- Subtle help text: "Automatically research your topic using web and social media search"

#### `frontend/src/views/SimulationStatus.vue` (modify)

When `job.enriched_seed` is present:
- Collapsible "Web Research" card below the pipeline progress section
- Shows the research summary text (rendered as prose)
- Citation links listed at the bottom of the card
- Card is collapsed by default, expands on click

When enrichment failed (job.enrich_web is true but enriched_seed is null, and job is still active):
- Subtle note: "Web research unavailable — running with your original seed"
- "Retry" button next to the note
- Retry calls `POST /api/jobs/{id}/enrich-retry`
- On success, the research card appears

#### `frontend/src/views/SimulationResults.vue` (modify)

In Story view, add a "Sources & Background" section at the bottom:
- Only shown when `job.enriched_seed` exists
- Renders the enrichment summary
- Lists citation links (clickable, open in new tab)

#### `frontend/src/api/jobs.js` (modify)

Add:
- `retryEnrichment(jobId)` — POST to `/api/jobs/{id}/enrich-retry`

### Error Handling

| Scenario | Behavior |
|----------|----------|
| xAI API failure | Log error, enriched_seed = null, show "unavailable" note with retry button |
| Timeout (30s) | Same as API failure |
| XAI_API_KEY not set | Skip enrichment silently (dev/test environments) |
| enrich_web = false | Skip entirely, no enrichment columns touched |
| Retry succeeds before pod job submission | Enriched seed used in pipeline |
| Retry succeeds after pod already started | Enrichment stored for display only, not used in current sim |

### Cost

- xAI search invocation: ~$0.005 per call
- Token cost (grok-4.20-reasoning): ~$0.02-0.05 per enrichment
- Total per simulation: ~$0.03-0.06
- Negligible relative to GPU cost ($0.86/hr) and credit price ($6-60 per sim)

### Data Flow

```
JobCreate { seed_text, goal, tier, enrich_web: true }
  |
  v
Celery: run_simulation_task()
  |-- provision GPU (async, returns pod_id)
  |-- enrich_seed(seed_text, goal)    <-- runs during vLLM warmup
  |     |-- xAI Responses API call
  |     |     tools: [web_search, x_search]
  |     |     model: grok-4.20-reasoning
  |     |-- returns EnrichmentResult(summary, citations)
  |-- _update_enrichment(job_id, summary, citations_json)
  |-- wait for health check to pass
  |-- POST /job to pod with combined seed:
  |     seed_text = original + "\n\n--- Background Research ---\n" + summary
  |
  v
Pod: run_pipeline(enriched_seed_text, goal, ...)
  |-- build_graph(enriched_seed_text, goal)  <-- Zep gets richer context
  |-- prepare_simulation(...)
  |-- run_and_wait(...)
  |-- generate_report(...)
  |
  v
Results stored, frontend displays enrichment in status + results views
```
