#!/usr/bin/env python3
"""Import demo JSON files as SimulationJob rows with share tokens.

Usage (on server):
    docker compose exec -T app python infra/scripts/import_demos.py
"""
import asyncio
import json
import secrets
import sys
from pathlib import Path
from datetime import datetime, timezone

# Make saas importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from simswarm.adapter import adapt_structured


def build_structured_payload(
    brief: str,
    findings: list[dict],
    chat_log: list[dict],
    graph_data: dict,
) -> str:
    """Demo-import wrapper — same contract as saas/jobs/tasks_report._build_structured.

    Uses simswarm.adapter.adapt_structured so demo rows carry the Path-3
    structured shape (brief, verdict, findings + deterministic signals) the
    frontend expects from live runs post-cutover.
    """
    return json.dumps(adapt_structured(
        brief=brief,
        findings=findings,
        chat_log=chat_log,
        graph_data=graph_data,
        forecast_days=30,  # TODO(task15): thread forecast_days from demo JSON
        verdict="",
    ))

DEMOS_DIR = Path(__file__).parent.parent.parent / "demos"
SYSTEM_USER_EMAIL = "demo@fishcloud.internal"


async def main():
    import bcrypt
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy import text
    import os

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)

    engine = create_async_engine(database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        # 1. Create or get system user
        result = await session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": SYSTEM_USER_EMAIL},
        )
        row = result.first()
        if row:
            user_id = str(row[0])
            print(f"System user exists: id={user_id}")
        else:
            pw_hash = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode()
            result = await session.execute(
                text(
                    "INSERT INTO users (email, password_hash, email_verified, created_at) "
                    "VALUES (:email, :pw, true, :ts) RETURNING id"
                ),
                {"email": SYSTEM_USER_EMAIL, "pw": pw_hash, "ts": datetime.now(timezone.utc)},
            )
            user_id = str(result.scalar())
            await session.commit()
            print(f"Created system user: id={user_id}")

        # 2. Import each demo JSON
        demo_files = sorted(DEMOS_DIR.glob("*.json"))
        if not demo_files:
            print("No demo JSON files found in demos/")
            return

        slug_to_token = {}

        for demo_file in demo_files:
            slug = demo_file.stem
            data = json.loads(demo_file.read_text(encoding="utf-8"))

            # Skip if already imported (check by goal + system user)
            goal = data.get("goal", slug)
            existing = await session.execute(
                text(
                    "SELECT id, share_token FROM simulation_jobs "
                    "WHERE user_id = :uid AND goal = :goal LIMIT 1"
                ),
                {"uid": user_id, "goal": goal},
            )
            existing_row = existing.first()
            if existing_row:
                token = existing_row[1]
                if not token:
                    token = secrets.token_urlsafe(32)
                    await session.execute(
                        text("UPDATE simulation_jobs SET share_token = :token WHERE id = :id"),
                        {"token": token, "id": existing_row[0]},
                    )
                    await session.commit()
                slug_to_token[slug] = token
                print(f"  {slug}: already imported (id={existing_row[0]}, token={token})")
                continue

            # Build job row from demo data
            report = data.get("report_markdown", "")
            chat_log = data.get("chat_log", [])
            graph_data = data.get("graph_data", {})
            token = secrets.token_urlsafe(32)

            chat_log_str = json.dumps(chat_log, ensure_ascii=False) if isinstance(chat_log, list) else str(chat_log)
            graph_str = json.dumps(graph_data, ensure_ascii=False) if isinstance(graph_data, dict) else str(graph_data)

            # Build structured payload via adapt_structured (same shape as live pipeline).
            # Fall back to safe defaults if brief/findings are absent.
            brief = data.get("brief", data.get("executive_brief", ""))
            findings = data.get("findings", [])
            _empty_graph = {"nodes": [], "edges": [], "metadata": {"entity_types": [], "total_nodes": 0, "total_edges": 0}}
            structured_str = build_structured_payload(
                brief=brief,
                findings=findings,
                chat_log=chat_log if isinstance(chat_log, list) else [],
                graph_data=graph_data if isinstance(graph_data, dict) else _empty_graph,
            )

            result = await session.execute(
                text(
                    "INSERT INTO simulation_jobs "
                    "(user_id, seed_text, goal, tier, credits_charged, status, "
                    " result_report, result_chat_log, result_graph, result_structured, "
                    " share_token, created_at, completed_at) "
                    "VALUES (:user_id, :seed, :goal, :tier, 0, 'COMPLETED', "
                    " :report, :chat_log, :graph, :structured, "
                    " :token, :ts, :ts) "
                    "RETURNING id"
                ),
                {
                    "user_id": user_id,
                    "seed": data.get("seed_summary", ""),
                    "goal": goal,
                    "tier": data.get("tier", "medium"),
                    "report": report,
                    "chat_log": chat_log_str,
                    "graph": graph_str,
                    "structured": structured_str,
                    "token": token,
                    "ts": datetime.now(timezone.utc),
                },
            )
            job_id = result.scalar()
            await session.commit()

            slug_to_token[slug] = token
            report_len = len(report)
            print(f"  {slug}: imported (id={job_id}, report={report_len} chars, token={token[:16]}...)")

        # 3. Output mapping
        print("\n=== Slug → Share Token Mapping ===")
        for slug, token in slug_to_token.items():
            print(f"  {slug}: /s/{token}")

        # Save mapping to file for frontend use
        mapping_file = DEMOS_DIR / "share_tokens.json"
        mapping_file.write_text(json.dumps(slug_to_token, indent=2), encoding="utf-8")
        print(f"\nMapping saved to {mapping_file}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
