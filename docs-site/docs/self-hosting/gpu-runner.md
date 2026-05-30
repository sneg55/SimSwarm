---
sidebar_label: GPU Runner
---

# GPU Runner

Simulations run on ephemeral GPU pods. A pod is provisioned per job, runs the engine plus an on-pod vLLM server, uploads its artifacts to MinIO, and is torn down. No GPU is kept warm between jobs.

## Provider abstraction

The provider layer lives in `saas/gpu/`. `provider.py` defines the abstract base `GPUProvider` with `provision`, `get_status`, `terminate`, and `execute_command`, plus two dataclasses:

- `GPUProviderConfig` — `gpu_type`, `docker_image`, `max_cost_per_hour_usd`, `timeout_seconds`, optional `env_vars`, `job_id`, and `cloud_type` (`ALL`, `SECURE`, or `COMMUNITY`).
- `GPUInstance` — `instance_id`, `provider`, `gpu_type`, `ip_address`, `ssh_port`, `status`, and an `is_ready` property.

**RunPod is the only GPU provider.** The job worker's provider factory
(`saas/workers/_get_gpu_provider`) returns `RunPodProvider` (`runpod_provider.py`), configured
with `RUNPOD_API_KEY`. The abstract `GPUProvider` base class (`saas/gpu/provider.py`) defines
the interface, so another provider could be added, but RunPod is the only one shipped and
supported.

## Provisioning (RunPod)

`RunPodProvider.provision` creates a pod and polls until it is ready:

- It tries the configured `gpu_type` first, then a fallback list of same-class and progressively cheaper GPU types until one has stock.
- It honors `cloud_type`: the configured pool first (e.g. `SECURE` for the large tier), then falls back to `ALL` if every GPU type is out of stock there.
- The pod is created without a network volume — at pod start, `start.sh` pulls the model weights from MinIO (`s3://$MINIO_BUCKET/models/hf-cache/*`), so it can schedule in any datacenter. No helper script ships for this upload yet; the operator must first upload the model's HuggingFace cache to the `models/hf-cache/` prefix manually (any S3-compatible client works — e.g. `s5cmd --endpoint-url "https://$MINIO_ENDPOINT" cp '/path/to/hf-cache/*' "s3://$MINIO_BUCKET/models/hf-cache/"`, the same layout the worker reads). If the MinIO env vars are missing or the pull fails, the pod falls back to a slower HuggingFace download. See [MinIO → Model weights](./minio.md#model-weights).
- The pod name encodes the job id (`fishcloud-sim-j{job_id}`) so orphan cleanup can recover the binding from RunPod metadata alone.
- Readiness is polled (up to `MAX_POLL_ATTEMPTS = 120` × 5s = 10 min). The worker API is reached over RunPod's HTTP proxy at `https://{pod_id}-5000.proxy.runpod.net`.

## Guaranteed teardown

Teardown is guaranteed in two places:

- During provisioning, the poll loop is wrapped so that cancellation (e.g. a Temporal activity timeout) terminates the pod before re-raising — a cancelled provision never leaks a billing pod.
- In the workflow, the GPU phase runs inside a `try` whose `finally` always calls the `terminate_pod` activity for whichever pod is currently held. Bad-host retries terminate and clear the reference in-loop, so the `finally` runs at most once per successful provision. See [Temporal](./temporal.md).

The legacy runner (`saas/jobs/runner.py`) follows the same pattern: it wraps pipeline execution in `try/finally` and terminates the pod in the `finally` block, guarding the terminate so a teardown failure does not mask the real error.

## Tier → GPU / model routing

Routing is data-driven. A `ModelRouting` row per tier (`small` / `medium` / `large`) maps the tier to a `model_id`, `gpu_type`, `max_rounds`, optional `vllm_args`, and `target_agents`. On job creation, `POST /api/jobs` looks up the routing row for the requested tier and fails with a 500 if none is configured. The resolved values are passed into the Temporal workflow's `SimParams`.

Tier constants live in `saas/constants/tiers.py` — the single source of truth for per-tier timeouts and the RunPod cloud-pool selection:

- `TIER_TIMEOUTS` — wall-clock cap for the run phase, in seconds: `small` 2700, `medium` 18000, `large` 43200.
- `TIER_CLOUD_TYPE` — `small`/`medium` use `ALL` (cheapest), `large` uses `SECURE` (tighter variance).
- Watchdogs and circuit breakers (`TIER_STUCK_THRESHOLD_S`, the LLM error-rate breaker, the slow-pod detector, and `MAX_CONSECUTIVE_POLL_FAILURES`) detect stuck, degraded, or unreachable pods and let the workflow swap or retry.
