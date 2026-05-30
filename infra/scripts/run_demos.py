#!/usr/bin/env python3
"""Run demo simulations on the production server via Temporal.

Meant to be run inside the app container. Bypasses auth and billing,
dispatches the SimulationWorkflow the same way POST /jobs does, and writes
result snapshots to demos/.

Usage (on server):
    cd /opt/fishcloud
    docker compose exec -T app python infra/scripts/run_demos.py [--slugs ... | --parallel | --dry-run | --list]

After a successful run, follow up with `promote_demos.py` to swing the share
tokens over to the fresh jobs and drop tokens from anything no longer in
DEMO_CONFIGS.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from refresh_demos import DEMO_CONFIGS, _load_seed_text  # noqa: E402

from demos_helpers import (  # noqa: E402
    async_database_url, build_storage, dispatch_demo, save_snapshot, wait_for_job,
)


async def _record_outcome(config, outcome, results):
    if outcome and len(outcome.get("report", "")) > 0:
        out = save_snapshot(config, outcome)
        print(f"  Saved: {out}")
        results[config["slug"]] = "OK"
    else:
        results[config["slug"]] = "FAILED"


async def run_all(configs, dry_run: bool, parallel: bool):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from saas.workflows.client import get_temporal_client

    engine = create_async_engine(async_database_url())
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    storage = None if dry_run else build_storage()
    temporal_client = None if dry_run else await get_temporal_client()

    results: dict[str, str] = {}
    dispatched: list = []

    try:
        for config in configs:
            seed_text = _load_seed_text(config)
            async with factory() as session:
                job_id = await dispatch_demo(
                    session, temporal_client, storage, config, seed_text, dry_run=dry_run,
                )
            if dry_run:
                results[config["slug"]] = "DRY_RUN"
                continue
            if job_id is None:
                results[config["slug"]] = "DISPATCH_FAILED"
                continue
            dispatched.append((config, job_id))

            if not parallel:
                outcome = await wait_for_job(factory, job_id, config["slug"])
                await _record_outcome(config, outcome, results)

        if parallel and dispatched:
            print(f"\nAll {len(dispatched)} workflows dispatched. Waiting on results...\n")
            tasks = [
                asyncio.create_task(wait_for_job(factory, jid, cfg["slug"]))
                for cfg, jid in dispatched
            ]
            outcomes = await asyncio.gather(*tasks, return_exceptions=True)
            for (cfg, _jid), outcome in zip(dispatched, outcomes):
                if isinstance(outcome, Exception):
                    print(f"  {cfg['slug']}: poller raised {outcome!r}")
                    results[cfg["slug"]] = "FAILED"
                    continue
                await _record_outcome(cfg, outcome, results)
    finally:
        await engine.dispose()

    return results


def main():
    p = argparse.ArgumentParser(description="Run demo sims via Temporal on the prod server")
    p.add_argument("--slugs", nargs="*", help="Specific demo slugs to run (default: all in DEMO_CONFIGS)")
    p.add_argument("--dry-run", action="store_true", help="Show what would be dispatched")
    p.add_argument("--list", action="store_true", help="List all demos and their status")
    p.add_argument("--parallel", action="store_true",
                   help="Dispatch all at once, then wait (more GPUs in flight)")
    args = p.parse_args()

    if args.list:
        from refresh_demos import list_demos
        list_demos()
        return

    slugs = args.slugs if args.slugs else [c["slug"] for c in DEMO_CONFIGS]

    configs = []
    for slug in slugs:
        config = next((c for c in DEMO_CONFIGS if c["slug"] == slug), None)
        if not config:
            print(f"Unknown demo slug: {slug}")
            sys.exit(1)
        configs.append(config)

    print(f"Running {len(configs)} demos (parallel={args.parallel}, dry_run={args.dry_run})")
    results = asyncio.run(run_all(configs, dry_run=args.dry_run, parallel=args.parallel))

    print(f"\n{'=' * 60}\nSUMMARY\n{'=' * 60}")
    for slug, status in results.items():
        print(f"  {slug}: {status}")

    ok = sum(1 for s in results.values() if s in {"OK", "DRY_RUN"})
    print(f"\n{ok}/{len(results)} succeeded")
    if ok < len(results) and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()
