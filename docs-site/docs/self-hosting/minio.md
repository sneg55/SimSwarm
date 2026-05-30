---
sidebar_label: MinIO
---

# MinIO

MinIO (or any S3-compatible store) holds per-job simulation artifacts and model weights. The application never streams large artifacts through itself — it hands out presigned URLs and lets the pod and browser read/write the object store directly.

## Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `MINIO_ENDPOINT` | Host:port of the MinIO server. Empty disables the storage layer. | `""` |
| `MINIO_ACCESS_KEY` | Access key. | `""` |
| `MINIO_SECRET_KEY` | Secret key. | `""` |
| `MINIO_BUCKET` | Bucket name for artifacts. | `simswarm` |
| `MINIO_SECURE` | Use TLS for connections. | `true` |
| `MINIO_PROXY_BASE` | Optional HTTPS proxy base to rewrite download URLs (avoids mixed-content blocks when the page is HTTPS but MinIO is HTTP), e.g. `https://simswarm.xyz/minio`. | `""` |

If `MINIO_ENDPOINT` is empty, `SimDataStorage` (`saas/storage/minio_client.py`) is disabled: upload/download URL generation returns `None`, and the sim-data endpoints respond 404 (`Object storage not configured`).

## How it is used

`SimDataStorage` generates presigned URLs scoped to a job:

- **Upload** — on job creation, `POST /api/jobs` generates presigned PUT URLs (`generate_upload_urls`, 14-hour expiry) for every artifact file, keyed under `sim-data/{job_id}/`. These are passed into the workflow so the pod can upload results directly.
- **Download** — `GET /api/jobs/{job_id}/sim-data` returns presigned GET URLs (`generate_download_urls`, 1-hour expiry) for the browser to fetch. When `MINIO_PROXY_BASE` is set, each URL is rewritten to route through the HTTPS reverse proxy.

## Artifact files

The artifacts written per job (`SIM_DATA_FILES`):

```
market_curves.json
agent_trajectories.json
engagement_summary.json
top_posts.json
posts.json
trades.json
social_graph.json
profiles.json
chat_log.json       # required by the off-pod report task (saas/jobs/tasks_report.py)
relations.json      # LLM-extracted typed graph edges
```

In production MinIO commonly runs on its own VPS. Set `MINIO_PROXY_BASE` when the app is served over HTTPS but MinIO is reached over plain HTTP, so browser downloads are not blocked as mixed content.

## Model weights

Besides per-job artifacts, MinIO also holds the on-pod LLM weights under the `models/hf-cache/` prefix. GPU pods pull these at start (the worker image does not bake them in), which avoids per-pod HuggingFace downloads and lets pods schedule in any datacenter. At pod start, `infra/docker/start.sh` runs `s5cmd cp "s3://$MINIO_BUCKET/models/hf-cache/*"` into the pod's `HF_HOME`, expecting the standard HuggingFace cache layout (`models--Qwen--Qwen3-14B/snapshots/{hash}/...`).

No helper script ships for this upload yet — you must do it manually before the first run. Upload the model's HuggingFace cache tree to the `models/hf-cache/` prefix in your MinIO bucket — the exact layout `start.sh` pulls from. Any S3-compatible client works; for example, with `s5cmd` (which the worker also uses):

```bash
AWS_ACCESS_KEY_ID="$MINIO_ACCESS_KEY" \
AWS_SECRET_ACCESS_KEY="$MINIO_SECRET_KEY" \
s5cmd --endpoint-url "https://$MINIO_ENDPOINT" \
      cp '/path/to/hf-cache/*' "s3://$MINIO_BUCKET/models/hf-cache/"
```

Here `/path/to/hf-cache/` is a local `HF_HOME` cache that already contains `models--<org>--<model>/snapshots/{hash}/` with the `*.safetensors` shards (e.g. produced by a one-time `huggingface-cli download` into that directory). Use `http://` instead of `https://` if `MINIO_SECURE` is `false`. If the prefix is empty or the pull fails, the pod falls back to a (much slower) HuggingFace download.
