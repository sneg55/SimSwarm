# Contributing to SimSwarm

Thanks for your interest! SimSwarm is MIT-licensed and self-hostable.

## Development setup

See the README for backend (`pip install -e ".[dev]"`) and frontend
(`cd frontend && npm install`) setup.

## Tests

- Backend: `pytest` (in-memory SQLite, no external services needed)
- Frontend: `cd frontend && npm test`

Please run both before opening a PR. Backend lints with Ruff (line length 100).

## Pull requests

- Branch off `main`, keep PRs focused.
- Don't commit secrets or infra hostnames/IPs.
- The engine lives in `simswarm/`; the SaaS-style app wrapper lives in `saas/`.

## Reporting issues

Open a GitHub issue with reproduction steps. For security issues, please
disclose privately rather than in a public issue.
