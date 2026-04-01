# Rich Simulation Data Extraction & Storage

**Date:** 2026-04-01
**Status:** Approved

## Problem

The MiroShark simulation engine produces rich per-agent data — every post, like, comment, follow, and prediction market trade across hundreds of rounds — in SQLite databases on the GPU worker pod. Currently we only return a thin summary (8-12 chat log entries, 9-20 graph nodes) via the /status response. When the pod terminates, all this data is lost. The result: our product looks like ChatGPT output instead of a browsable simulated ecosystem.

## Solution

Extract structured data from the GPU worker's SQLite databases, upload to self-hosted MinIO object storage via presigned URLs, and serve to the frontend via SimSwarm API. The existing /status response stays unchanged — rich data is a separate, non-fatal data path.

## Architecture

```
GPU Worker Pod                SimSwarm (Hetzner)           MinIO VPS
─────────────                ──────────────────           ─────────

1. POST /job receives         Generates presigned
   presigned upload URLs ←──  upload URLs from MinIO

2. Runs simulation
   (MiroShark pipeline)

3. Extracts data from
   SQLite DBs into JSON

4. Uploads files         ─────────────────────────────→  Stores in
   via presigned URLs                                    simswarm/sim-data/{job_id}/

5. Returns /status with
   report + chat_log +
   graph_data + structured
   (unchanged from today)

                              6. Frontend requests    ──→  Serves via
                                 sim data via              presigned
                                 GET /api/jobs/{id}/       download URLs
                                 sim-data
```

## MinIO Infrastructure

- Separate VPS, single Docker container
- Bucket: `simswarm`, prefix: `sim-data/{job_id}/`
- ILM lifecycle policy: auto-delete objects after 90 days
- Access: SimSwarm generates presigned URLs (PUT for upload, GET for download)
- GPU worker never gets MinIO credentials — only presigned URLs
- Frontend never talks to MinIO directly — gets presigned download URLs from SimSwarm API
- Config: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` in SimSwarm `.env`

## Data Files

### Chart-ready files (small, pre-computed for direct frontend rendering)

| File | Size est. | Content |
|------|-----------|---------|
| `market_curves.json` | 2-20KB | Per round per market: `{ round, market_id, question, price_yes, price_no, volume }` |
| `agent_trajectories.json` | 5-50KB | Per agent per round window: `{ agent_id, name, type, rounds: [{ round, posts, likes_received, followers, sentiment }] }` |
| `engagement_summary.json` | 2-10KB | Per round: `{ round, total_posts, total_likes, total_comments, active_agents, top_post }` |
| `top_posts.json` | 10-50KB | Top 50 posts by engagement: `{ post_id, agent_name, platform, content, likes, comments, round }` |

### Bulk browsable files (larger, fetched on-demand when user drills in)

| File | Size est. | Content |
|------|-----------|---------|
| `posts.json` | 100KB-5MB | All posts with engagement counts, agent info, platform, round |
| `trades.json` | 50KB-2MB | All prediction market trades with price, shares, cost |
| `social_graph.json` | 10-100KB | Follow edges with timestamps + detected coalition groups |
| `profiles.json` | 20-100KB | Agent profiles: bio, stance, influence_weight, initial beliefs |

### Total upload size per tier

| Tier | Agents | Rounds | Estimated total |
|------|--------|--------|-----------------|
| Small | 25 | 200 | 200KB - 2MB |
| Medium | 60 | 500 | 2MB - 20MB |
| Large | 150 | 1000 | 20MB - 100MB |

## Agent Sentiment Derivation

Agent `stance` in the current system is static (set once in config). To track actual opinion evolution, we derive sentiment per agent per round window using the existing lexicon-based scoring from `score_entity_sentiment()`, applied to each agent's posts within a round window (e.g., every 20 rounds). This goes into `agent_trajectories.json` as the `sentiment` field.

## Data Flow — Step by Step

1. **Job creation** — SimSwarm generates presigned PUT URLs for all 8 files
2. **Celery dispatch** — `upload_urls` dict passed in `run_simulation_task.delay()`
3. **JobConfig** — new `upload_urls: dict[str, str] | None` field
4. **GPU worker `/job` POST** — receives `upload_urls` alongside existing fields
5. **Pipeline runs** — simulation produces SQLite DBs as normal
6. **Post-pipeline extraction** — new step in run_job.py after simulation, before report. Opens SQLite DBs, queries data, writes JSON to temp dir
7. **Upload** — worker HTTP PUTs each JSON file to its presigned URL. Failure is non-fatal
8. **Report generation** — unchanged
9. **`/status` response** — adds `"sim_data_uploaded": true/false` flag, everything else unchanged
10. **SimSwarm stores result** — saves report/chat_log/graph_data as today. Sets `sim_data_available=true` on job row
11. **Frontend requests** — `GET /api/jobs/{id}/sim-data` returns presigned download URLs, frontend fetches files directly

## Failure Handling

MinIO upload failure does NOT fail the job. The simulation result (report, chat_log, graph_data) still flows through the existing /status → Celery path. `sim_data_available` stays false, frontend shows the same experience as today. Errors are logged but not raised.

## SimSwarm Backend Changes

### New files
- `saas/storage/minio_client.py` — MinIO client wrapper, presigned URL generation (upload + download)

### Modified files
- `saas/models/job.py` — add `sim_data_available: bool` column (default false)
- `saas/schemas/jobs.py` — add `sim_data_available` to response schemas
- `saas/api/jobs.py` — generate upload URLs at job creation, pass through Celery
- `saas/workers/tasks.py` — accept and forward `upload_urls` kwarg
- `saas/workers/job_runner.py` — add `upload_urls` to JobConfig, pass in `/job` POST body, set `sim_data_available` from /status response

### New API endpoint
- `GET /api/jobs/{id}/sim-data` — returns `{ files: { "market_curves.json": "https://minio.../presigned...", ... } }` or 404 if `sim_data_available` is false

### New migration
- Add `sim_data_available` boolean column to `simulation_jobs`

## GPU Worker Changes (infra/docker/)

### run_job.py — new extraction functions

All functions open the simulation SQLite DBs read-only and produce JSON:

- `extract_posts(sim_dir)` → `posts.json` — query post + user tables across twitter/reddit DBs
- `extract_trades(sim_dir)` → `trades.json` — query trade table from polymarket DB
- `extract_market_curves(sim_dir)` → `market_curves.json` — reconstruct price timeline from trade history + initial reserves
- `extract_agent_trajectories(sim_dir, actions)` → `agent_trajectories.json` — per-agent per-round-window: post count, likes received, follower count, derived sentiment
- `extract_engagement_summary(sim_dir, actions)` → `engagement_summary.json` — per-round totals
- `extract_top_posts(sim_dir)` → `top_posts.json` — top 50 by engagement
- `extract_social_graph(sim_dir)` → `social_graph.json` — follow edges + coalitions from mutual follows
- `extract_profiles(sim_dir)` → `profiles.json` — agent profiles from CSV/JSON files

### run_job.py — upload step

After extraction, before report generation:
```python
if upload_urls:
    for filename, url in upload_urls.items():
        filepath = output_dir / filename
        if filepath.exists():
            requests.put(url, data=filepath.read_bytes(), headers={"Content-Type": "application/json"})
```

### worker_api.py

- Accept `upload_urls` in `/job` POST body
- Pass to run_job pipeline
- Add `sim_data_uploaded` to `/status` response

## Scope Boundaries

**In scope:**
- MinIO Docker setup + ILM policy (90-day retention)
- `saas/storage/minio_client.py` (presigned URL generation)
- New SimSwarm API endpoint `GET /api/jobs/{id}/sim-data`
- DB: `sim_data_available` boolean column on `simulation_jobs`
- GPU worker extraction functions (8 JSON files from SQLite DBs)
- GPU worker upload via presigned URLs
- Passing upload_urls through Celery → JobConfig → `/job` POST
- Non-fatal failure handling

**Out of scope (separate future specs):**
- Frontend components (charts, feed browser, graph visualization)
- Postgres queryable tables (future upgrade from pre-computed JSON)
- MinIO clustering / HA
- Data backfill for existing completed simulations
