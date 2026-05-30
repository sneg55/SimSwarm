---
sidebar_label: First Simulation
---

# Run Your First Simulation

This walks through the end-user flow on a full self-hosted instance (`DEMO_MODE=false`). On a read-only demo instance, register and launch are blocked with a 403 — see [Demo Mode](../self-hosting/demo-mode.md).

## 1. Register and sign in

Create an account from the **Register** page. Registration requires an email and a password of at least 8 characters. A verification link is generated for the address (logged by the email backend in a default install). You receive a session token on successful registration and can sign in afterward from the **Login** page.

## 2. Open the new-simulation wizard

The wizard (`NewSimulation.vue`) has three steps, shown by the progress bar at the top.

### Step 1 — Seed document

Paste or type your seed text. This is the source material the agents reason about. The seed has a maximum length of 50,000 characters (`MAX_SEED_CHARS`), shown by the live character counter.

The **Enrich with web research** toggle is on by default (`enrich_web=true`). When enabled, the seed is augmented with live web and X/Twitter research before the simulation runs.

### Step 2 — Prediction goal

Enter the prediction goal — the question the simulation should answer (for example, a forecast of market or sentiment movement). Set the **forecast horizon in days**; it is required and must be between 1 and 365.

### Step 3 — Launch

Pick a simulation tier (small / medium / large), which controls agent scale and the GPU/model routing. Click **Run Simulation** to submit.

Submitting calls `POST /api/jobs` with `seed_text`, `goal`, `tier`, `enrich_web`, and `forecast_days`. The API:

1. Rejects the request with 403 if the instance is in demo mode.
2. Rejects seeds over the character limit (400) and duplicate in-flight submissions of the same seed/goal/tier within a 60-second window (409).
3. Creates the job row, generates presigned MinIO upload URLs, and starts a Temporal `SimulationWorkflow` (`id=sim-{job_id}`).

You can also save a partial wizard as a **draft** and resume it later.

## 3. Watch progress

After launch you are taken to the status view. The job moves through statuses owned by the Temporal workflow: `PENDING` → `PROVISIONING` → `RUNNING` → `REPORTING` → `COMPLETED` (or `FAILED`). Behind the scenes the workflow performs optional seed enrichment, market derivation, GPU pod provisioning, the simulation run, artifact upload to MinIO, and off-pod report generation. The status endpoint reflects the live pipeline stage.

## 4. Open results

When the job reaches `COMPLETED`, open it to see the result views:

- **Story** — narrative overview: the question, a verdict, stakeholder positions, and the findings the simulation surfaced.
- **Graph** — interactive Cytoscape entity graph of agents and their interactions (`GET /api/jobs/{job_id}/graph`).
- **Data** — prediction-market and simulation-data charts, backed by presigned MinIO downloads (`GET /api/jobs/{job_id}/sim-data`).
- **Report** — the deep analysis report with citations.

Completed jobs can be turned into a public **share link** (`/s/{token}`) for read-only viewing.
