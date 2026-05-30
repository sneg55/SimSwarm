---
sidebar_label: Demo Mode
---

# Demo Mode

Demo mode turns an instance into a read-only public showcase. It is controlled by a single flag.

## The flag

`DEMO_MODE` is a boolean `Settings` field (`saas/config.py`), default `false`:

- `false`: full self-hosted platform; signups and job submission are allowed.
- `true`: read-only demo; registration, job creation, and draft launch are blocked.

Set it in `.env`:

```bash
DEMO_MODE=true
```

## What it gates

When `DEMO_MODE=true`, three write paths return 403 with the message `This is a read-only demo. Deploy your own instance to run simulations.`:

- `POST /api/auth/register`: registration (`saas/auth/api.py`).
- `POST /api/jobs`: create a new simulation (`saas/jobs/api.py`).
- Draft launch (`saas/jobs/api_draft.py`).

Login and all read paths (browsing jobs, share links, results) remain available.

## Exposed to the frontend

The current flag is exposed publicly so the UI can hide write actions:

```
GET /api/config  →  {"demo_mode": <bool>}
```

`PublicConfig` (`saas/health.py`) returns just `demo_mode`. The frontend reads this to adapt navigation and disable the wizard.

## Use case

Run a public instance (such as the one at [simswarm.xyz](https://simswarm.xyz)) with `DEMO_MODE=true` so visitors can explore curated and shared results without being able to register or consume GPU resources. For a private or internal instance where users run their own simulations, leave it `false`.
