# External LLM Report Generation — Design

**Date:** 2026-04-13
**Status:** Approved
**Scope:** Move report generation off the GPU pod to a Celery-side task calling an external flagship LLM (Anthropic Claude Opus 4.6 by default), with full credit refund on any failure before `COMPLETED`.

---

## 1. Motivation

Today, report generation runs on the GPU pod after the simulation finishes (`infra/docker/run_job_v2.py`, which calls `run_job_v2_runner.py:generate_report()`). The pod's `smart_llm` — which the MiroShark README identifies as the appropriate place to route a flagship cloud model — currently points at the same local vLLM as `fast_llm`. This couples three things that should be independent:

1. **Pod lifetime** — the GPU stays provisioned during report gen (30-120s of idle cost while an LLM-bound task runs).
2. **Report quality** — constrained to whatever weights the pod runs (today: Qwen3-14B).
3. **Report reliability** — a pod crash after the sim completes loses the entire job, because artifacts exist only on pod disk until the report is written.

The MiroShark README directly endorses routing report generation to a cloud model when reasoning quality matters. This design implements that split.

## 2. Goals and non-goals

**Goals**

- Report generation runs off-pod, using a flagship external LLM (default: Claude Opus 4.6).
- Pod teardown happens as soon as simulation artifacts are in MinIO — before report generation begins.
- Report generation uses Anthropic prompt caching to keep Opus cost bounded (~$0.05-0.25 per report).
- Any failure before `status=COMPLETED` results in a 100% credit refund.
- Worker restarts during the report phase are recoverable, matching the existing `recover_stale_jobs` pattern.

**Non-goals**

- Changing `simswarm/report.py` or its prompt. The SaaS-side report runner ports the same 5-turn tool loop and same `report.j2` template.
- Supporting multiple external providers in the first cut. The `AnthropicClient` sits alongside `simswarm.llm.LLMClient` but there is no provider-abstraction layer beyond choosing one at config time.
- Interactive ReportAgent chat (MiroShark's step 5). The split enables this as a later feature but it is not in scope here.
- Changing the on-pod `smart_llm` that Engine uses for high-reasoning agent turns during the simulation. That stays pointed at local vLLM.

## 3. Architecture

### 3.1 High-level flow

```
Celery task                  Pod (GPU)                  External LLM
-----------                  ---------                  ------------
provision pod   ───────────► run_simulation()
                             write artifacts to disk
                             upload artifacts to MinIO
                             return "sim_complete"
terminate pod   ◄───────────
transition job to
status=REPORTING

generate_report_task:
  load artifacts from MinIO
  AnthropicClient.chat()  ───────────────────────────► Claude Opus 4.6
  (5-turn tool loop,
   prompt caching on)
  write report.md to MinIO +
  DB fields
transition job to
status=COMPLETED
```

### 3.2 Architectural commitments

1. **The pod no longer generates reports.** `run_job_v2.py:run_pipeline` stops calling `generate_report()` and stops writing `report.md` and `structured_results.json`. Sim artifacts (`chat_log.json`, `posts.json`, `trades.json`, `agent_trajectories.json`, `social_graph.json`, `engagement_summary.json`, `graph_data.json`, `summary.json`) are still written and still uploaded to MinIO.

2. **Report generation moves to a separate Celery task**, chained after `run_simulation_task`. This is the key decoupling: the pod is torn down as soon as artifacts are uploaded, not after report generation.

3. **A new `saas/jobs/report.py` module** holds `ReportRunner`, which ports the 5-turn tool loop from `simswarm/report.py` and reads artifacts from MinIO instead of a live `SimulationResult` object.

4. **A new `saas/adapters/anthropic_client.py`** implements the same `chat(messages, tools) → LLMResponse` interface as `simswarm.llm.LLMClient`, against Anthropic's Messages API. It adds `cache_control: {"type": "ephemeral"}` markers on the system prompt and tool schemas — the primary cost-reduction mechanism for the 5-turn loop.

5. **New job status `REPORTING`** is added to the `JobStatus` enum. Pod-phase failures still resolve to `FAILED + REFUNDED`. Report-phase failures resolve the same way (see §6).

## 4. Components

### 4.1 New files

**`saas/adapters/anthropic_client.py`** (~120 lines)

- Class `AnthropicClient` with signature `chat(messages, tools) → LLMResponse`, matching `simswarm.llm.LLMClient` exactly so the 5-turn loop code is source-identical.
- Translates OpenAI-style inputs into Anthropic Messages API format: `system` is extracted into a top-level field, tool schemas are passed through (Anthropic's shape is a near-subset of OpenAI's), assistant `tool_calls` round-trip to `tool_use` blocks, and `tool` role messages round-trip to `tool_result` blocks.
- Applies `cache_control: {"type": "ephemeral"}` markers to the system prompt and to the tool schema array. Both are static across the 5-turn loop; cached input tokens are billed at 10% of the normal input rate.
- Uses the `anthropic` Python SDK, version-pinned (see `feedback_pin_worker_deps`).
- Implements a `close()` no-op for interface parity with `LLMClient`.
- Translates Anthropic errors (`rate_limit_error`, `overloaded_error`, 5xx) into distinct exception types the Celery retry logic can classify as transient.

**`saas/jobs/report.py`** (~180 lines)

- Class `ReportRunner`. Constructor takes `job_id` and an artifact-fetcher callable.
- `run()`:
  1. Pulls required artifacts from MinIO: `chat_log.json`, `posts.json`, `trades.json`, `agent_trajectories.json`.
  2. Builds a `ReportArtifacts` dataclass — the MinIO-sourced equivalent of `SimulationResult`.
  3. Instantiates `AnthropicClient` from env config.
  4. Runs the 5-turn tool loop (ported verbatim from `simswarm/report.py`).
  5. Writes `report.md` to MinIO and persists `result_report`, `result_structured`, `key_insight` to the DB via the existing sync psycopg2 path (`_save_job_results`).
- Raises `ReportArtifactsMissingError` if required MinIO artifacts are absent, `ReportExhaustedError` if the loop terminates without final markdown.

**`saas/jobs/report_tools_minio.py`** (~100 lines)

- `ReportTools` variant with identical public surface to `simswarm.report_tools.ReportTools` (`get_top_posts`, `get_coalitions`, `get_agent_summary`, `get_trajectory`, `dispatch`, `tool_schemas`), but backed by MinIO-sourced JSON dicts instead of a typed `SimulationResult`. Parallel class rather than a data-shape adapter to keep both call sites readable.

**`saas/jobs/tasks_report.py`** (~80 lines)

- Celery task `generate_report_task(job_id)`, registered with Celery autodiscovery.
- Retry policy: 5 attempts with delays `[30s, 120s, 300s, 900s, 1800s]`. Total retry window ~55 minutes.
- Retries only on transient exception types raised by `AnthropicClient` (rate limit, overload, 5xx, network timeout). Permanent errors (invalid request, missing artifacts, exhausted loop) fail immediately.
- On success: sets job status to `COMPLETED`, sets `completed_at`, updates `key_insight`, writes all report-derived fields.
- On terminal failure: sets status to `FAILED`, issues 100% refund via `_refund_credits`, records `error_message`.

### 4.2 Modified files

**`infra/docker/run_job_v2.py`** — `run_pipeline()` removes the `generate_report()` call, removes `report.md` and `structured_results.json` writes. `summary.json` gains `report_pending: true` in place of `report_length`.

**`infra/docker/run_job_v2_runner.py`** — `_SMART_MODEL` / `smart_llm` plumbing stays on the `run_simulation` path (Engine still uses it for high-reasoning agent turns). `generate_report()` is removed from this file.

**`infra/docker/worker_api.py`** — `_upload_sim_data` retry policy tightened: each MinIO PUT gets 3 attempts with 2s backoff before surfacing an upload failure. Under the new flow, upload failure is fatal because the pod no longer returns an inline report.

**`saas/jobs/models.py`** — Adds `REPORTING` to `JobStatus` enum. Alembic migration uses the `ALTER TYPE ADD VALUE` pattern with explicit `COMMIT/BEGIN` wrapping (see `feedback_alembic_enum`).

**`saas/jobs/tasks.py`** — `run_simulation_task`, on successful completion with `sim_data_uploaded=True`: persists non-report fields, transitions the job to `REPORTING`, enqueues `generate_report_task.apply_async((job_id,))`. Does *not* mark `COMPLETED` — that is the report task's responsibility. On `sim_data_uploaded=False`: job marked `FAILED`, 100% refund, report task not enqueued.

**`saas/jobs/recovery.py`** — `recover_stale_jobs` extends to cover jobs stuck in `REPORTING` with no active Celery task. For such jobs, re-enqueues `generate_report_task`. This handles worker-restart races during the report phase, matching the existing pattern for `RUNNING` state.

**`saas/config.py`** — New settings: `smart_provider` (default `"anthropic"`), `smart_model` (default `"claude-opus-4-6"`), `anthropic_api_key` (required when provider is `anthropic`).

**`saas/constants/tiers.py`** — Adds `TIER_REPORT_TIMEOUT_S = {"small": 300, "medium": 600, "large": 900}`. Used by `ReportRunner` as a wall-clock cap on the tool loop, independent of the GPU tier timeout.

### 4.3 Optional (defer if scope pressure)

**`ModelRouting` table** — add nullable `report_model` column so operators can override Opus → Sonnet per tier without a deploy. Matches the existing operator-configurable routing pattern. Not required for the first cut.

### 4.4 Explicitly not touched

- `simswarm/report.py` and `simswarm/report_tools.py` stay as-is. They remain the standalone-library reference implementation (see `project_engine_rewrite`).
- `saas/adapters/mirofish_adapter.py` stays untouched — it targets the v1 pipeline and is on its way out.

## 5. Data flow (happy path)

| Step | Actor | State transition | Persisted |
|------|-------|------------------|-----------|
| 1 | API | Job created, credits debited | `status=PENDING` |
| 2 | Celery `run_simulation_task` | GPU provisioning | `status=PROVISIONING`, `pod_id` |
| 3 | Pod | Sim running, artifacts accumulating on pod disk | `status=RUNNING`, `pipeline_stage` updates |
| 4 | Pod | Sim done, artifacts uploaded to MinIO via presigned PUTs | `sim_data_uploaded=true` in `/status` response |
| 5 | Celery `run_simulation_task` | Persists non-report fields, enqueues report task, terminates pod | `status=REPORTING`, `result_chat_log`, `result_graph`, etc. |
| 6 | Celery `generate_report_task` | Pulls artifacts from MinIO, runs 5-turn Opus loop | (no status change) |
| 7 | Celery `generate_report_task` | Writes `report.md` to MinIO, persists report fields | `status=COMPLETED`, `completed_at` |

### 5.1 Artifact contract

The following MinIO artifacts are the input contract for report generation, uploaded by the pod before it reports `sim_data_uploaded=true`:

- `chat_log.json` — required by `ReportTools`
- `posts.json` — required
- `agent_trajectories.json` — required
- `trades.json` — used for Market Analysis section
- `social_graph.json`, `engagement_summary.json`, `graph_data.json`, `summary.json` — used by frontend graph views, not by report gen

Invariant: **`sim_data_uploaded=true` implies the artifact set is sufficient to generate the report.** This invariant is what makes the pod/Celery split safe.

`structured_results.json` is no longer written by the pod; it is synthesized by `ReportRunner` after report generation and written to MinIO + DB.

## 6. Failure modes and refund policy

### 6.1 Refund rule

**Any failure before `status=COMPLETED` results in a 100% credit refund**, via the existing `_refund_credits` path. There is no partial refund case.

This rule folds all failure classes below into a single refund behavior and removes the need for an operator-configurable refund fraction.

### 6.2 Failure modes

| ID | Scenario | Resolution |
|----|----------|------------|
| F1 | Report task fails on transient error (rate limit, 5xx, timeout) | Celery retries 5× with `[30s, 120s, 300s, 900s, 1800s]` backoff. Total window ~55 min. |
| F2 | Artifacts missing from MinIO at report time | Should not occur (enqueue gated on `sim_data_uploaded=true`). If it does, mark `FAILED`, 100% refund, emit alert — indicates pod-side contract bug. |
| F3 | Report task exhausts retries | Mark `FAILED`, `error_message="report_generation_failed: <reason>"`, 100% refund. |
| F4 | Pod sim succeeds but artifact upload fails (`sim_data_uploaded=false`) | Mark `FAILED`, 100% refund, emit alert. Mitigated by pod-side retry on MinIO PUTs (3 attempts, 2s backoff). |
| F5 | Anthropic returns malformed tool call or loop fails to terminate | 5-turn cap (`_MAX_ROUNDS = 5`) already enforced. If loop exits without final markdown, raise `ReportExhaustedError` → F3. |
| F6 | Pod crashes mid-sim, recovery resumes and completes | Existing `tasks_resume.py` path. After successful resume, it enqueues the report task via the same code path as the normal flow. Single branch point. |
| F7 | Worker restart between pod teardown and report task enqueue | `recover_stale_jobs` extends to pick up `REPORTING` jobs with no active Celery task and re-enqueue `generate_report_task`. Load-bearing under the 100% refund rule — without it, a worker restart would cost the full pod price. |

### 6.3 Implications of the 100% refund rule

- Report retries should be aggressive (reflected in the 5-attempt, 55-minute retry window). Cost of retries is negligible vs. losing a full sim's credits.
- F7 recovery is a first-class requirement, not a nice-to-have. `recover_stale_jobs` extension is required for this design to ship.

## 7. Cost model

Per-report cost at flagship quality (measured from `simswarm/report.py` 5-turn loop with realistic tool output sizes):

| Tier | Sim scale | Input tokens | Output tokens | Opus cost (uncached) | Opus cost (cached) |
|------|-----------|--------------|---------------|----------------------|--------------------|
| Small | 15 rounds, 5 agents | ~6K | ~1.5K | $0.20 | ~$0.05 |
| Medium | 50 rounds, 10 agents | ~15K | ~2.5K | $0.41 | ~$0.11 |
| Large | 200 rounds, 20 agents | ~40K | ~3K | $0.83 | ~$0.22 |

Cached costs assume Anthropic's `ephemeral` cache hits on the static system prompt + tool schemas across turns 2-5 of the loop. The first turn pays full price for the cache write; subsequent turns pay 10% for cache hits.

Compare against the 30-120s GPU-idle cost this design saves: $0.008-0.03 on L40S, $0.025-0.10 on H100 SXM. Caching makes Opus strictly cheaper than the H100 idle cost it replaces at small and medium tiers.

## 8. Testing

### 8.1 Unit tests

- `tests/adapters/test_anthropic_client.py` — request-shape translation, `cache_control` placement, tool-call round-trip, error classification. Mocked via `httpx.MockTransport`. No network calls.
- `tests/jobs/test_report_tools_minio.py` — behavior parity with `simswarm.report_tools.ReportTools`, using canned MinIO artifact fixtures.
- `tests/jobs/test_report.py` — `ReportRunner.run()` with a stub `AnthropicClient` returning scripted responses. Covers: successful completion, loop exhaustion (`ReportExhaustedError`), missing artifacts (`ReportArtifactsMissingError`).

### 8.2 Integration tests

- `tests/jobs/test_tasks_report.py` — end-to-end Celery task flow with `db_session` + `funded_user` fixtures. Happy path, retry exhaustion + 100% refund, F7 recovery via `recover_stale_jobs`.
- `tests/jobs/test_tasks_chaining.py` — `run_simulation_task` → `generate_report_task` chaining. Asserts the chain is enqueued on `sim_data_uploaded=true` and the job is failed + refunded when `sim_data_uploaded=false`.

### 8.3 Fixtures

`tests/fixtures/artifacts/small_sim/` — real small-tier MinIO artifacts exported from a production run (~100KB). Per `feedback_no_fake_data`, no synthesized data. Reused as regression fixtures for future report-prompt tweaks.

### 8.4 Out of scope

- Real Anthropic API calls in CI (mock at the HTTP boundary).
- MinIO round-trips (stub the storage layer; infra tests cover MinIO).
- Prompt quality evaluation (prompt is unchanged from existing implementation).

### 8.5 Operational verification (manual, post-deploy)

Per `feedback_test_deploys_thoroughly`, this change requires manual verification beyond CI:

1. Run one job at each tier after deploy; confirm report appears, `status=COMPLETED`, no refund issued.
2. Force a report failure (invalid `ANTHROPIC_API_KEY` in staging) and verify the job reaches `FAILED` with full refund.
3. Trigger a deploy (worker restart) while a sim is mid-flight and confirm both the sim and the subsequent report phase recover correctly.

## 9. Rollout

1. Ship `AnthropicClient` + unit tests behind no feature flag — dormant code path.
2. Ship `ReportRunner` + `tasks_report.py` + Alembic migration for `REPORTING` enum value and (optional) `ModelRouting.report_model` column. Still dormant.
3. Ship modified `run_job_v2.py` (pod stops writing report) + modified `run_simulation_task` (enqueues report task) in a single deploy. At this point the new path is live.
4. Manual verification (§8.5). If any of the three checks fail, revert via git — the design does not introduce irreversible schema changes beyond an additive enum value.

No feature-flag gating mid-deploy because the pod code and Celery code must flip atomically — the pod stops producing `report.md` and Celery starts expecting to generate it. A gate would require both paths to coexist, which doubles the surface area for bugs.
