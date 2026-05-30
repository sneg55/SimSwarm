#!/usr/bin/env python3
"""Sync demo share tokens to match the curated DEMO_CONFIGS list.

For each goal in DEMO_CONFIGS: find the newest COMPLETED demo-user job,
attach a share token if it has none (carrying forward an older token for the
same goal when one exists so old /s/<token> URLs keep working), then revoke
share tokens from any older same-goal jobs.

For every other demo-user job (goal not in DEMO_CONFIGS): revoke share token.

Run after `run_demos.py` finishes, on the prod server:

    cd /opt/fishcloud
    docker compose exec -T app python infra/scripts/promote_demos.py [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import secrets
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from refresh_demos import DEMO_CONFIGS  # noqa: E402

from demos_helpers import async_database_url, DEMO_USER_EMAIL  # noqa: E402


async def run(dry_run: bool) -> int:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(async_database_url())
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    goals = [c["goal"] for c in DEMO_CONFIGS]
    if len(set(goals)) != len(goals):
        print("ERROR: DEMO_CONFIGS contains duplicate goals — promote uses goal as identity")
        return 1

    try:
        async with factory() as session:
            user_row = (
                await session.execute(
                    text("SELECT id FROM users WHERE email = :email"),
                    {"email": DEMO_USER_EMAIL},
                )
            ).first()
            if not user_row:
                print(f"No demo user ({DEMO_USER_EMAIL}); nothing to promote.")
                return 0
            user_id = str(user_row[0])

            for goal in goals:
                rows = (
                    await session.execute(
                        text(
                            "SELECT id, status, share_token, created_at "
                            "FROM simulation_jobs "
                            "WHERE user_id = :uid AND goal = :goal "
                            "ORDER BY created_at DESC"
                        ),
                        {"uid": user_id, "goal": goal},
                    )
                ).all()
                def _status_value(raw):
                    return raw.value if hasattr(raw, "value") else str(raw)

                completed = [r for r in rows if _status_value(r[1]) == "COMPLETED"]
                if not completed:
                    print(f"  SKIP {goal!r}: no COMPLETED job yet")
                    continue

                target = completed[0]
                target_id, _status, target_token, _created = target
                inherited_token = next(
                    (r[2] for r in rows if r[2] and r[0] != target_id),
                    None,
                )

                if target_token:
                    print(f"  KEEP  job {target_id}: token unchanged ({target_token[:12]}…)")
                elif inherited_token:
                    print(f"  MOVE  token {inherited_token[:12]}… → job {target_id}")
                    if not dry_run:
                        await session.execute(
                            text("UPDATE simulation_jobs SET share_token = NULL WHERE share_token = :t"),
                            {"t": inherited_token},
                        )
                        await session.execute(
                            text("UPDATE simulation_jobs SET share_token = :t WHERE id = :id"),
                            {"t": inherited_token, "id": target_id},
                        )
                else:
                    new_token = secrets.token_urlsafe(32)
                    print(f"  MINT  token {new_token[:12]}… → job {target_id}")
                    if not dry_run:
                        await session.execute(
                            text("UPDATE simulation_jobs SET share_token = :t WHERE id = :id"),
                            {"t": new_token, "id": target_id},
                        )

                older_with_token = [r for r in rows if r[0] != target_id and r[2]]
                for r in older_with_token:
                    print(f"  STRIP token {r[2][:12]}… from older job {r[0]}")
                    if not dry_run:
                        await session.execute(
                            text("UPDATE simulation_jobs SET share_token = NULL WHERE id = :id"),
                            {"id": r[0]},
                        )

            placeholders = ", ".join(f":g{i}" for i in range(len(goals)))
            params = {f"g{i}": g for i, g in enumerate(goals)}
            params["uid"] = user_id
            stale = (
                await session.execute(
                    text(
                        "SELECT id, goal FROM simulation_jobs "
                        f"WHERE user_id = :uid AND share_token IS NOT NULL AND goal NOT IN ({placeholders})"
                    ),
                    params,
                )
            ).all()
            for sid, sgoal in stale:
                print(f"  DROP  share_token on job {sid} (goal not in DEMO_CONFIGS: {sgoal!r})")
                if not dry_run:
                    await session.execute(
                        text("UPDATE simulation_jobs SET share_token = NULL WHERE id = :id"),
                        {"id": sid},
                    )

            if not dry_run:
                await session.commit()
    finally:
        await engine.dispose()

    print("Dry run." if dry_run else "Done.")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="Print intended changes without writing")
    args = p.parse_args()
    sys.exit(asyncio.run(run(args.dry_run)))


if __name__ == "__main__":
    main()
