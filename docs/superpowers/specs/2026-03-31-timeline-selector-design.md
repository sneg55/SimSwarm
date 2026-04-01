# Timeline Selector for Simulation Creation

**Date:** 2026-03-31
**Status:** Approved

## Problem

The simulation config generator infers the forecast timeframe from free-text goal parsing. This is unreliable (LLM may misinterpret) and invisible to the user. There's no way for users to explicitly control how far into the future the simulation forecasts, and no connection between timeframe and tier capabilities.

## Solution

Add a timeline preset selector to Step 2 (Goal) of the simulation wizard. Pass the selected `forecast_days` as an explicit field through the full stack to the config generator.

## Presets

| Label | Days | Min rounds needed | Fits tier |
|-------|------|-------------------|-----------|
| 1 day | 1 | 100 | small+ |
| 1 week | 7 | 150 | small+ |
| 30 days | 30 | 200 | small+ |
| 90 days | 90 | 400 | medium+ |
| 6 months | 180 | 700 | medium+ |
| 1 year | 365 | 1000 | large only |

## Frontend

### TimelineChips.vue (new component)

- Row of pill-shaped chips in `frontend/src/components/wizard/`
- Single-select, emits `update:modelValue` with days as integer (or null)
- Props: `modelValue` (number | null)
- All chips enabled on Step 2 (no tier gating here)
- Small label above: "Forecast timeline"
- Styled to match existing wizard aesthetic (ocean-abyss bg, ocean-cyan active state)

### WizardGoal.vue (modified)

Layout order:
1. Textarea (goal)
2. TimelineChips
3. GoalQualityMeter
4. GoalTemplateCards

New props: `forecastDays`, emits `update:forecastDays`

### GoalQualityMeter.vue (modified)

- Accept optional `timelineDays` prop (number | null)
- If `timelineDays` is set, the TIMEFRAME_RE criterion is auto-satisfied
- Timeframe tip suppressed when a chip is selected

### WizardLaunch.vue (modified — Step 3 tier gating)

- Accept `forecastDays` prop
- Tier cards that can't handle the selected timeline get dimmed with a message: "Needs Medium for 90-day forecasts" (or similar)
- Tier → max forecast days mapping: `{ small: 30, medium: 180, large: 365 }`
- If no timeline selected, all tiers remain enabled (backward compatible)

### NewSimulation.vue (modified)

- New `forecastDays` ref (default: null)
- Pass to WizardGoal as v-model
- Pass to WizardLaunch as prop for tier gating
- Include in `createJob()` payload: `forecast_days: forecastDays.value`

## Backend

### Schema — `saas/schemas/jobs.py`

Add to `JobCreate`:
```python
forecast_days: int | None = None
```

### DB model — `saas/models/job.py`

Add column:
```python
forecast_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

### Migration

Alembic migration to add `forecast_days` nullable integer column to `simulation_jobs`.

### API — `saas/api/jobs.py`

- Store `forecast_days` on the job row
- Pass `forecast_days` as kwarg to `run_simulation_task.delay()`

### Worker — `saas/workers/tasks.py`

- Accept `forecast_days` kwarg
- Pass to GPU worker's `/job` POST body
- Config generator uses `forecast_days` directly when set, falls back to LLM parsing from goal text when null

## Data Flow

```
TimelineChips (30) -> WizardGoal -> NewSimulation -> createJob API
-> POST /api/jobs { seed_text, goal, tier, enrich_web, forecast_days: 30 }
-> DB: simulation_jobs.forecast_days = 30
-> Celery task(forecast_days=30) -> GPU /job { forecast_days: 30 }
-> Config generator: use 30 days directly, skip LLM timeframe parsing
```

## Backward Compatibility

- `forecast_days` is nullable everywhere (schema, DB, worker)
- Existing jobs without `forecast_days` continue to work (LLM parses from goal text)
- Timeline selector defaults to null (no chip selected) — wizard works identically to today if user skips it
