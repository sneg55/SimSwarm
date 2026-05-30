---
sidebar_label: Repository Structure
---

# Repository structure

SimSwarm is organized by feature. Each feature directory under `saas/` owns its
own models, schemas, API routes, and business logic, rather than splitting the
codebase by layer. The simulation engine is a separate native package.

## Top-level layout

```
saas/            # FastAPI application wrapper (this is the SaaS-style layer)
frontend/src/    # Vue 3 SPA
simswarm/        # The simulation engine (native package)
infra/           # Docker GPU worker, operational scripts
tests/           # pytest + pytest-asyncio
docs-site/       # This documentation site (Docusaurus)
```

## `saas/`: application layer

Feature directories co-locate everything that feature needs:

| Path | Responsibility |
| --- | --- |
| `saas/auth/` | Auth: api, models (`User`), schemas, service, email, profile. |
| `saas/jobs/` | Jobs: api, models (`SimulationJob`, `ModelRouting`, `ErrorEvent`), schemas, runner, tasks, persistence, enrichment, progress, export, share, fetch, ai, and more. |
| `saas/gpu/` | GPU provider: abstract base, RunPod implementation, error classification. |
| `saas/adapters/` | External-LLM adapter — the Anthropic client (`anthropic_client.py`) used for report generation. |
| `saas/storage/` | MinIO S3-compatible storage client + downloader. |
| `saas/constants/` | Named constants (tiers, timeouts, markers). |
| `saas/workflows/` | Temporal workflow + activities + worker. |
| `saas/workers/` | Celery app config + shared async utils. |
| `saas/middleware/` | Error tracking. |
| `saas/models/` | Base model class + re-exports for Alembic discovery. |
| `saas/config.py` | Pydantic Settings. |
| `saas/database.py` | Async SQLAlchemy engine/session. |
| `saas/router.py` | API router assembly. |
| `saas/health.py` | Health-check endpoint. |
| `saas/main.py` | FastAPI app factory. |

Note: a `saas/billing/` directory still exists but is empty (only a
`__pycache__`); billing was removed in the open-source pivot.

## `frontend/src/`: Vue SPA

| Path | Responsibility |
| --- | --- |
| `views/` | Page components. |
| `components/` | Reusable components (`graph/`, `wizard/`, `results/`, `data/`). |
| `composables/` | Shared Composition API logic. |
| `stores/` | Pinia stores. |
| `api/` | Axios clients. |

## The engine: `simswarm/`, not `vendor/`

The simulation engine is a native package at `simswarm/`. There is no
`vendor/` directory and no vendored engine submodule. When contributing to engine behavior (environments, belief
formulation, extractors, graph building), work in `simswarm/`. The application
talks to the engine through `saas/adapters/`. See
[Engine Internals](../engine/architecture.md).

## File-size norm

Keep files small and focused, under roughly 300 lines. Many features are split
into multiple files for this reason (for example, `saas/jobs/` has separate
`api.py`, `api_draft.py`, `api_retry.py`, `api_share.py`, and several
`persistence_*.py` modules). Prefer adding a focused module over growing an
existing file past the norm.

## Related

- [System Overview](../architecture/system-overview.md): how these pieces run.
- [Code Style](code-style.md): conventions within this structure.
