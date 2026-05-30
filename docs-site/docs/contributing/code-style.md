---
sidebar_label: Code Style
---

# Code Style

Beyond linting, SimSwarm has a handful of conventions that keep the codebase
consistent and the runtime correct. These come from the project's architecture
rules and are worth following in any contribution.

## Linting

Backend code is linted with **Ruff** at **line length 100** (`[tool.ruff]` in
`pyproject.toml`). Run Ruff and both test suites before opening a PR — see
[Testing](testing.md).

## Feature co-location

Organize by feature, not by layer. Each feature owns its models, schemas, API
routes, and business logic in one directory (`saas/auth/`, `saas/jobs/`,
`saas/gpu/`, …). Keep files under roughly 300 lines; split into focused modules
rather than growing one file. See [Repository Structure](repo-structure.md).

## App factory + dependency injection

The FastAPI app is built by a factory, `saas.main:create_app(settings=None)`,
which accepts an optional `Settings` so tests can inject their own
configuration. Database access goes through the injectable
`saas.database:get_session` dependency, which tests override with an in-memory
SQLite session. Follow this pattern: depend on `get_session` rather than
reaching for a global engine, so the code stays testable.

## Sync DB writes from Celery/activities

When writing to the database from a Celery task or a Temporal activity, use
**synchronous psycopg2** — never the shared async SQLAlchemy pool. Mixing the
async pool into worker/activity contexts causes `InterfaceError` and can wedge
the event loop. The job persistence layer (`saas/jobs/persistence*.py`) exposes
sync helpers for exactly this reason, and the workflow activities persist
results at the source using them.

## Cancel, not terminate, for Temporal

To stop a running workflow, use **`workflow cancel`**, never `workflow
terminate`. Termination skips the workflow's `finally` block — and that
`finally` is what tears the GPU pod down (`fishcloud.terminate_pod` in
`SimulationWorkflow`). Skipping it leaves the pod running and billing. Cancel
lets the cleanup path execute. See [Data Flow](../architecture/data-flow.md) and
[Temporal](../self-hosting/temporal.md).

## Engine via the adapter layer

The simulation engine lives in `simswarm/`. The application talks to it through
`saas/adapters/`. Keep engine concerns out of the application feature
directories and vice versa.

## No credit gating

The open-source build has **no billing and no credit gating**. Job creation
does not check or charge a balance — there is no 402 path. Some legacy
billing artifacts remain on disk (an empty `saas/billing/` directory, the dead
`credits_charged` column, and the retained `REFUNDED` status), but they are not
part of any active path. Do not reintroduce credit checks. See
[Database Schema](../architecture/database-schema.md).

## Related

- [Repository Structure](repo-structure.md)
- [Testing](testing.md)
- [Data Flow](../architecture/data-flow.md)
