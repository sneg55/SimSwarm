---
sidebar_label: Database Schema
---

# Database Schema

The application database is PostgreSQL. Models are defined with SQLAlchemy 2.0
typed mappings on a shared `Base` (`saas/models/base.py`). This page documents
the core tables. Columns are taken directly from the model files
(`saas/auth/models.py`, `saas/jobs/models.py`); only the schema-significant
fields are described.

Migrations are managed with Alembic (`alembic upgrade head`, run by the
one-shot `migrate` service). See [Migrations](../self-hosting/migrations.md).

## `users` — `saas/auth/models.py`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int | PK, autoincrement. |
| `email` | varchar(255) | Unique, indexed. |
| `password_hash` | varchar(255) | bcrypt hash. |
| `created_at` | timestamptz | Defaults to now (UTC). |
| `email_verified` | bool | Defaults to `False`. |
| `verification_token` | varchar(255) | Nullable. |
| `reset_token` | varchar(255) | Nullable. |
| `reset_token_expires` | timestamptz | Nullable. |

## `simulation_jobs` — `saas/jobs/models.py`

The central table. One row per simulation job.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int | PK, autoincrement. |
| `user_id` | varchar(255) | Indexed. |
| `seed_text` | text | The seed document. |
| `goal` | text | Nullable prediction goal. |
| `tier` | varchar(20) | Nullable; maps to a `model_routing` row. |
| `credits_charged` | int | **Dead column** — see below. Defaults to `0`. |
| `status` | enum `JobStatus` | Defaults to `PENDING`. |
| `pipeline_stage` | int | Nullable; pipeline progress marker. |
| `result_report` | text | Nullable; report markdown. |
| `result_chat_log` | text | Nullable; agent chat log JSON. |
| `result_graph` | text | Nullable; entity graph JSON. |
| `result_structured` | text | Nullable; structured results payload JSON. |
| `error_message` | text | Nullable; failure reason. |
| `gpu_provider` | varchar(50) | Nullable. |
| `gpu_cost_usd` | float | Nullable. |
| `created_at` | timestamptz | Defaults to now (UTC). |
| `completed_at` | timestamptz | Nullable. |
| `pod_id` | varchar(255) | Nullable, indexed. |
| `celery_task_id` | varchar(255) | Nullable. |
| `workflow_id` | varchar(255) | Nullable, indexed; the Temporal workflow id. |
| `workflow_run_id` | varchar(255) | Nullable. |
| `retry_count` | int | Defaults to `0`. |
| `retry_of` | int | Nullable; id of the job this is a retry of. |
| `provision_seconds` | int | Nullable. |
| `pipeline_seconds` | int | Nullable. |
| `key_insight` | varchar(200) | Nullable; one-line takeaway. |
| `share_token` | varchar(64) | Nullable, unique, indexed; public share link. |
| `last_heartbeat` | timestamptz | Nullable; liveness for the stale-job detector. |
| `enrich_web` | bool | Defaults to `True`. |
| `enriched_seed` | text | Nullable; the enriched seed. |
| `enrichment_citations` | text | Nullable. |
| `forecast_days` | int | Nullable; prediction horizon. |
| `sim_data_available` | bool | Defaults to `False`; set true once artifacts land in MinIO. |
| `live_status` | JSON | Nullable; live progress snapshot. |
| `resume_task_id` | varchar(255) | Nullable. |
| `markets_config` | JSON | Nullable; the per-sim derived prediction markets. |

### `JobStatus` enum

`DRAFT`, `PENDING`, `PROVISIONING`, `RUNNING`, `REPORTING`, `COMPLETED`,
`FAILED`, `REFUNDED`.

### Dead-but-retained billing artifacts

The open-source pivot removed billing/credits, but two billing artifacts were
kept to avoid invasive PostgreSQL schema surgery (notably the hassle of
removing a value from an existing enum type):

- `credits_charged`: retained as a dead column that always stays `0`. Its
  default lets inserts omit it.
- `REFUNDED` status: retained as a `JobStatus` enum value. It is no longer
  reached by normal job flow, but report-task idempotency still treats it as a
  terminal state alongside `COMPLETED` and `FAILED`.

Neither is part of any active code path that charges or refunds; there is no
billing in the OSS build.

## `model_routing` — `saas/jobs/models.py`

Operator-configurable map from tier to model and GPU. Single source of truth
read at job creation. Tier configuration is seeded in tests via the
`seeded_routing` fixture.

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int | PK, autoincrement. |
| `sim_tier` | varchar(20) | Unique. |
| `model_id` | varchar(255) | HF model id (e.g. `Qwen/Qwen3-14B`). |
| `gpu_type` | varchar(50) | e.g. `NVIDIA L40S`. |
| `max_rounds` | int | Defaults to `200`. |
| `vllm_args` | text | Nullable; extra vLLM flags. |
| `target_agents` | int | Defaults to `5`. |

## `error_events` — `saas/jobs/models.py`

Captures unhandled errors for diagnosis (written by the error-tracking
middleware and other call sites).

| Column | Type | Notes |
| --- | --- | --- |
| `id` | int | PK, autoincrement. |
| `timestamp` | timestamptz | Defaults to now (UTC). |
| `level` | varchar(20) | Defaults to `ERROR`. |
| `source` | varchar(20) | `api`, `worker`, or `gpu`. |
| `message` | text | Error message. |
| `traceback` | text | Nullable. |
| `user_id` | varchar(255) | Nullable. |
| `job_id` | int | Nullable. |
| `request_path` | varchar(500) | Nullable. |

## Related

- [Data Flow](data-flow.md): how rows transition between statuses.
- [Migrations](../self-hosting/migrations.md): Alembic operations.
