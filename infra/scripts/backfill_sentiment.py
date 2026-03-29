#!/usr/bin/env python3
"""One-shot script: backfill sentiment scores on all jobs missing them.

Usage (on server):
  docker compose exec app python infra/scripts/backfill_sentiment.py

Usage (local, if DB is accessible):
  DATABASE_URL=postgresql+asyncpg://... python infra/scripts/backfill_sentiment.py
"""
import asyncio
import json
import os
import sys

# Ensure the project root is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from saas.utils.sentiment import score_entity_sentiment, needs_sentiment_backfill

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://fishcloud:fishcloud@db:5432/fishcloud",
)


async def main():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import text

    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        rows = (await session.execute(
            text("""
                SELECT id, result_graph, result_chat_log
                FROM simulation_jobs
                WHERE result_graph IS NOT NULL
                ORDER BY id
            """)
        )).fetchall()

        print(f"Found {len(rows)} jobs with graph data")

        updated = 0
        skipped = 0
        no_nodes = 0

        for job_id, result_graph, result_chat_log in rows:
            try:
                graph_data = json.loads(result_graph)
            except (json.JSONDecodeError, TypeError):
                print(f"  job {job_id}: invalid JSON, skipping")
                skipped += 1
                continue

            if not needs_sentiment_backfill(graph_data):
                skipped += 1
                continue

            nodes = graph_data.get("nodes", [])
            if not nodes:
                no_nodes += 1
                continue

            chat_log = json.loads(result_chat_log) if result_chat_log else []
            score_entity_sentiment(graph_data, chat_log)

            scored = sum(1 for n in nodes if n.get("sentiment", 0) != 0)
            print(f"  job {job_id}: {scored}/{len(nodes)} nodes scored")

            await session.execute(
                text("UPDATE simulation_jobs SET result_graph = :g WHERE id = :id"),
                {"g": json.dumps(graph_data), "id": job_id},
            )
            updated += 1

        await session.commit()

    await engine.dispose()
    print(f"\nDone: {updated} updated, {skipped} already had sentiment, {no_nodes} had no nodes")


if __name__ == "__main__":
    asyncio.run(main())
