# Draft Campaigns — Resume Editing Wizard

**Issue:** #68
**Date:** 2026-04-09

## Problem

Users who start creating a simulation but navigate away lose all wizard progress. They must re-enter seed text, goal, and tier from scratch.

## Solution

Add a `DRAFT` status to the job lifecycle. The wizard auto-saves a draft on each step transition. Users can resume drafts from the dashboard. Credits are only deducted at launch.

## Data Model

### JobStatus Enum

Add `DRAFT` before `PENDING`:

```python
class JobStatus(str, Enum):
    DRAFT = "DRAFT"          # New
    PENDING = "PENDING"
    PROVISIONING = "PROVISIONING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"
```

### SimulationJob Column Changes

Make two columns nullable for drafts:

| Column | Current | Change |
|--------|---------|--------|
| `goal` | `String, NOT NULL` | `nullable=True` |
| `tier` | `String, NOT NULL` | `nullable=True` |

All other columns already accept NULL or have defaults. `credits_charged` stays 0 for drafts (set at launch).

### Alembic Migration

Single migration: add `DRAFT` to the status CHECK constraint (PostgreSQL enum), alter `goal` and `tier` to nullable.

## API Endpoints

### POST /jobs/draft

Create a new draft with partial data. No credit check.

**Request:**
```json
{
  "seed_text": "Apple is developing...",
  "enrich_web": true
}
```

All fields optional except `seed_text` (must be non-empty if provided). `goal`, `tier`, `forecast_days` accepted but not required.

**Response:** `201 Created` — Full `JobResponse` with `status: "DRAFT"`, `credits_charged: 0`.

**Auth:** Required. Draft is owned by the authenticated user.

### PATCH /jobs/draft/{id}

Update an existing draft. Only works when `status == DRAFT`.

**Request:** Any subset of `{seed_text, goal, tier, enrich_web, forecast_days}`.

**Validation:**
- Job must exist and belong to current user
- Job must have `status == DRAFT`
- `seed_text` validated against MAX_SEED_CHARS if provided
- `tier` validated against TierEnum if provided

**Response:** `200 OK` — Updated `JobResponse`.

**Errors:**
- 404: Job not found or not owned by user
- 409: Job is not a draft (already launched)

### POST /jobs/draft/{id}/launch

Transition a complete draft to PENDING and start the simulation. This reuses the existing credit deduction, routing validation, and Celery dispatch logic from POST /jobs.

**Request:** Empty body. All data comes from the saved draft.

**Preconditions:**
- Job must have `status == DRAFT`
- `seed_text`, `goal`, `tier` must all be non-empty
- User must have sufficient credits for the tier
- Model routing must exist for the tier

**Flow:**
1. Validate all required fields are present → 422 if incomplete
2. Validate model routing exists for tier → 500 if missing
3. Debit credits atomically → 402 if insufficient
4. Set `credits_charged`, generate upload URLs
5. Dispatch Celery task → rollback on failure
6. Set `status = PENDING`, store `celery_task_id`
7. Commit and return

**Response:** `200 OK` — Updated `JobResponse` with `status: "PENDING"`.

**Errors:**
- 404: Not found / not owned
- 409: Not a draft
- 422: Incomplete draft (missing seed_text, goal, or tier)
- 402: Insufficient credits

### Existing Endpoints — Changes

**POST /jobs** — Unchanged. Still works as a direct create-and-launch for users who complete the wizard in one session.

**GET /jobs** — Drafts are included in the list response. Frontend filters them into a separate section. No backend filtering change needed.

**DELETE /jobs/{id}** — Already works for any status. No change needed.

## Frontend

### Wizard Flow (NewSimulation.vue)

**Creating a new simulation (no draft param):**

1. Step 1 → user enters seed → clicks Next
   - Call `POST /jobs/draft` with `{seed_text, enrich_web}`
   - Store returned `draftId` in component state
   - Advance to step 2
2. Step 2 → user enters goal → clicks Next
   - Call `PATCH /jobs/draft/{draftId}` with `{goal, forecast_days}`
   - Advance to step 3
3. Step 3 → user selects tier → clicks Launch
   - Call `PATCH /jobs/draft/{draftId}` with `{tier}` (save tier choice)
   - Call `POST /jobs/draft/{draftId}/launch`
   - On success: deduct credits locally, navigate to `/sim/{id}`
   - On 402: show insufficient credits error
   - On 422: show "incomplete draft" error (shouldn't happen in normal flow)

**Navigating backward:** Allowed freely. No API call needed — data is already saved.

**Leaving the wizard mid-flow:** Draft is already persisted from the last completed step transition. No "unsaved changes" warning needed.

### Resuming a Draft

**Route:** `/new?draft={id}`

**On mount:**
1. If `draft` query param exists, fetch `GET /jobs/{id}`
2. Verify `status == DRAFT` and user owns it
3. Populate reactive state: `seedText`, `goal`, `tier`, `enrichWeb`, `forecastDays`
4. Compute starting step:
   - Has `goal`? → step 3 (tier selection)
   - Has `seed_text`? → step 2 (goal input)
   - Otherwise → step 1
5. Set `draftId` so subsequent Next clicks call PATCH instead of POST

**Step transitions when resuming:** Same PATCH calls as above. The draft already has an ID.

### Dashboard (DashboardView.vue)

**Draft section:**
- Query: filter jobs where `status === "DRAFT"` from the existing paginated list
- Display above "Active" jobs section
- Each draft card shows:
  - Goal text (truncated) or "Untitled draft" if no goal yet
  - Tier badge if selected, otherwise "No tier selected"
  - "Draft" status badge (muted style, not red/green)
  - Created date
  - Click → navigates to `/new?draft={id}`
  - Delete action (three-dot menu or swipe)
- Section hidden when no drafts exist

## What This Does NOT Include

- **Auto-save on text input** — Only saves on step transitions (Next button). No debounce/keypress saves.
- **Conflict detection** — If user opens same draft in two tabs, last write wins. Acceptable for MVP.
- **Draft expiration** — Drafts persist indefinitely. Can add cleanup later if needed.
- **Credit reservation** — No credits held for drafts. Checked only at launch.
- **Offline/localStorage fallback** — Drafts require network. If POST /draft fails, user sees an error.

## Testing

### Backend
- Create draft with partial data → 201, status=DRAFT, credits_charged=0
- Update draft fields → 200, fields updated
- Launch complete draft → 200, status=PENDING, credits deducted
- Launch incomplete draft (missing goal) → 422
- Launch draft with insufficient credits → 402
- Update non-draft job → 409
- Launch non-draft job → 409
- Delete draft → 204
- List jobs includes drafts

### Frontend
- Wizard step 1 Next creates draft via API
- Wizard step 2 Next updates draft via API
- Wizard step 3 Launch transitions draft to PENDING
- Navigate away and back → draft appears on dashboard
- Click draft on dashboard → wizard opens at correct step with data pre-filled
- Delete draft from dashboard → removed from list
