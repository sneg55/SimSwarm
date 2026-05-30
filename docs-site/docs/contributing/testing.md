---
sidebar_label: Testing
---

# Testing

SimSwarm has a backend pytest suite and a frontend Vitest suite. Neither
requires external services — the backend runs against in-memory SQLite.

## Backend

```bash
pytest
```

Configuration (`pyproject.toml`):

- **`asyncio_mode = "auto"`** — tests are written with `pytest-asyncio` and
  async functions are collected automatically (no per-test decorator needed).
- **`testpaths = ["tests"]`**.
- Coverage is configured with a **`fail_under = 90`** gate over the `saas`
  package (`pytest-cov`); `saas/main.py` and `saas/workers/celery_app.py` are
  omitted, along with tests/migrations.

### Test database

Tests use **in-memory SQLite via `aiosqlite`** (`TEST_DATABASE_URL =
"sqlite+aiosqlite://"` in `tests/conftest.py`) — no Postgres needed. The schema
is created from `Base.metadata` per engine fixture and dropped afterward.

### Fixtures (`tests/conftest.py`)

| Fixture | What it provides |
| --- | --- |
| `client` | An async httpx `AsyncClient` wired to the app via `ASGITransport`, with `get_session` overridden to the test SQLite session. |
| `db_session` | An `AsyncSession` against the in-memory engine. |
| `auth_headers` | Registers a test user and returns `Authorization: Bearer …` headers (plus the user id). |
| `funded_user` | The authenticated user's id. (Named for legacy reasons — there are no credits in the OSS build, so jobs are free.) |
| `seeded_routing` | Seeds the `ModelRouting` rows (`small`/`medium`/`large`) that job creation requires. |

An autouse `reset_rate_limiter` fixture resets the shared slowapi limiter
before and after every test so counters don't leak across cases.

## Frontend

```bash
cd frontend && npm test          # vitest run
cd frontend && npm run test:coverage
```

`npm test` runs Vitest once (`vitest run`). `npm run test:coverage` runs with
the coverage reporter. There is also a Playwright end-to-end suite
(`npm run test:e2e`).

## Linting

Backend code is linted with **Ruff** at **line length 100** (`[tool.ruff]` in
`pyproject.toml`). Run both test suites and lint before opening a PR.

## No fake data

Never generate fake or mock data for demos or feature testing — use only real
data from actual simulation runs. The one exception is unit/integration test
mocks, which are fine. This keeps demo content and feature validation honest.

## Related

- [Dev Setup](dev-setup.md) — installing dependencies.
- [Code Style](code-style.md) — conventions enforced beyond linting.
