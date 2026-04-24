# Restart-sim kebab option — design

One-line: add a **Restart** item to the `SimCard` kebab that pre-fills the wizard with the source sim's settings via an existing draft; user launches from the usual wizard flow.

## Motivation

The LLM-market derivation fix just shipped and several in-flight sims ran with the old goal-fallback code path. Users currently have no one-click way to re-run those sims with the same seed/goal/tier — they'd have to copy-paste the seed into a fresh wizard. The restart action also generalizes to "run this again" for any terminal sim.

## UX

- Kebab lives on `frontend/src/components/SimCard.vue`; today it has only **Delete**.
- Add **Restart** above Delete.
- Visible when `job.status ∈ {COMPLETED, FAILED, REFUNDED}`. Hidden for RUNNING/PROVISIONING/PENDING.
- Click: close menu → create draft from source → `router.push('/sim/new?draft=<id>')`. Wizard hydrates and the user confirms on the existing Launch button (which shows credit cost).

No new confirmation dialog. The wizard's Launch step is the confirmation.

## Data flow

```
SimCard (kebab click)
  └── emit('restart', job) ──► Dashboard.handleRestart(job)
        └── createDraft({
              seed_text,
              goal,
              tier,
              enrich_web,
              forecast_days: job.forecast_days ?? 30,
            })
        └── router.push('/sim/new?draft=' + draft.id)
```

Fields copied from the source `JobResponse` into the new draft:

| field          | source                                 | fallback |
|----------------|----------------------------------------|----------|
| `seed_text`    | `job.seed_text`                        | —        |
| `goal`         | `job.goal`                             | —        |
| `tier`         | `job.tier`                             | —        |
| `enrich_web`   | `job.enrich_web`                       | `true`   |
| `forecast_days`| `job.forecast_days`                    | `30`     |

Nothing else copies. Specifically:

- `markets_config` is re-derived per sim — not copied.
- No `retry_of` lineage is set. Restart is a fresh sim by design; the failed-sim `/retry` endpoint is the only path that sets `retry_of`.

## Backend

No changes. The existing `POST /jobs/draft` + `POST /jobs/draft/{id}/launch` endpoints cover this. `DraftCreate` (`saas/jobs/schemas.py:41`) already accepts every field we send.

## Frontend changes

1. **`SimCard.vue`**
   - `defineEmits(['delete', 'restart'])`.
   - `canRestart` computed: `['COMPLETED', 'FAILED', 'REFUNDED'].includes(job.status)`.
   - New menu button above Delete. Refresh-arrow SVG (two curved arrows) in `text-ocean-cyan` to differentiate from the coral Delete.
   - Handler: close menu, emit `'restart'` with the full `job`.
2. **`Dashboard.vue`**
   - `@restart="handleRestart"` on both `<SimCard>` usages (lines 92 and 102).
   - `async function handleRestart(job)`:
     ```js
     try {
       const draft = await createDraft({
         seed_text: job.seed_text,
         goal: job.goal,
         tier: job.tier,
         enrich_web: job.enrich_web,
         forecast_days: job.forecast_days ?? 30,
       })
       router.push(`/sim/new?draft=${draft.id}`)
     } catch (err) {
       // toast via existing error pattern; leave user on dashboard
     }
     ```
3. **`api/jobs.js`** — no change (`createDraft` already exists).

## Edge cases

- **Draft-create fails (network/auth)** — surface via the same error affordance the dashboard already uses for delete failures; no partial state.
- **Source `forecast_days` is null** (legacy rows) — fall back to 30, matching `saas/jobs/api_retry.py:42`.
- **Source job row lacks `seed_text` in `JobSummary`** — `JobSummary` (used for the dashboard job list) does not include `seed_text`. We need to either (a) fetch the full job via `getJob(id)` before `createDraft`, or (b) add `seed_text` to `JobSummary`. Picking **(a)** — fetch on click — avoids payload bloat on the list endpoint.
- **User already has an open draft in the wizard** — a fresh draft is created on purpose; the stale one stays orphaned (matches current behavior when a user re-navigates to `/sim/new`).

## Testing

- `frontend/src/components/__tests__/SimCard.spec.js`:
  - Kebab shows **Restart** for `COMPLETED`, `FAILED`, `REFUNDED`.
  - Kebab hides **Restart** for `RUNNING`, `PROVISIONING`, `PENDING`.
  - Clicking **Restart** emits `'restart'` with the job object and closes the menu.
- New or existing Dashboard spec:
  - `handleRestart` calls `createDraft` with exactly the five fields above, using `30` when `forecast_days` is null.
  - On success, navigates to `/sim/new?draft=<id>`.
  - On failure, does not navigate.

## Out of scope

- Any deep-link lineage ("restarted from sim #123") in the UI.
- Auto-kicking the wizard straight to Launch without user click.
- Restarting in-flight sims (RUNNING/PROVISIONING/PENDING).
