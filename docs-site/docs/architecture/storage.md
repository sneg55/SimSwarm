---
sidebar_label: Storage
---

# Storage

SimSwarm uses MinIO (S3-compatible) for two distinct purposes: the rich
artifacts a simulation produces, and the model weights a GPU pod loads at
startup. Both live in the same bucket (default `simswarm`) under different
prefixes. The code is in `saas/storage/`.

## Bucket layout

```
<bucket>/
  sim-data/<job_id>/
    market_curves.json
    agent_trajectories.json
    engagement_summary.json
    top_posts.json
    posts.json
    trades.json
    social_graph.json
    profiles.json
    chat_log.json
    relations.json
    report.md            # written by the report task after the sim
  models/
    hf-cache/
      models--Qwen--Qwen3-14B/snapshots/<hash>/...
```

## Simulation artifacts

The per-job artifact set is defined once in `SIM_DATA_FILES`
(`saas/storage/minio_client.py`) and lives under `sim-data/<job_id>/`:

| File | Contents |
| --- | --- |
| `market_curves.json` | Prediction-market price curves over the run. |
| `agent_trajectories.json` | Per-agent stance/state over rounds. |
| `engagement_summary.json` | Aggregate engagement metrics. |
| `top_posts.json` | Highest-signal posts. |
| `posts.json` | All posts. |
| `trades.json` | Market trades. |
| `social_graph.json` | Agent follow/interaction graph. |
| `profiles.json` | Agent personas/profiles. |
| `chat_log.json` | Full chat log — required by the off-pod report task (`saas/jobs/tasks_report.py`, which fetches artifacts via `saas/storage/minio_download.py` and drives the `ReportRunner` in `saas/jobs/report.py`). |
| `relations.json` | LLM-extracted typed graph edges (useful for post-mortems). |

### How artifacts move

- **Upload (pod → MinIO):** at job creation the API presigns PUT URLs for every
  file in `SIM_DATA_FILES` (`SimDataStorage.generate_upload_urls`,
  14-hour expiry) and hands them to the workflow. The GPU pod uploads directly,
  so artifacts never pass through the API or Temporal.
- **Download for the browser:** `GET /api/jobs/{job_id}/sim-data` (`saas/jobs/api.py`)
  returns presigned GET URLs (1-hour expiry) — but only when the job's
  `sim_data_available` flag is set. If a `proxy_base` is configured, download
  URLs are rewritten to route through the HTTPS reverse proxy, avoiding
  mixed-content blocks when the page is HTTPS but MinIO is plain HTTP.
- **Server-side read:** the report task fetches artifacts in-process with the
  MinIO SDK rather than presigned URLs (`fetch_artifact` in
  `saas/storage/minio_download.py`), and writes the finished `report.md` back to
  `sim-data/<job_id>/report.md` with `put_report_md`.

`SimDataStorage` is a no-op when `MINIO_ENDPOINT` is unset — `generate_*_urls`
return `None` and the sim-data endpoint responds 404 ("Object storage not
configured").

## Model weights

GPU pods do not download model weights from Hugging Face on the hot path.
Instead, the HF cache tree is pre-staged in MinIO under `models/hf-cache/` and
pulled at pod start. The pod's `infra/docker/start.sh` clears any stale
pre-seed, then uses `s5cmd` to recursively copy
`s3://<bucket>/models/hf-cache/*` into the pod's `HF_HOME`, preserving the
`models--<org>--<name>/snapshots/<hash>/` layout that vLLM and
`huggingface_hub` expect. If the MinIO pull fails, the pod falls back to
downloading from Hugging Face.

## Configuration

MinIO is configured via `MINIO_*` settings/environment variables
(`MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`,
`MINIO_SECURE`, `MINIO_PROXY_BASE`). See [MinIO](../self-hosting/minio.md) and
[Environment Reference](../self-hosting/env-reference.md).

## Related

- [Data Flow](data-flow.md) — when uploads and downloads happen.
- [MinIO](../self-hosting/minio.md) — operating the object store.
- [GPU Runner](../self-hosting/gpu-runner.md) — pod startup and weight loading.
