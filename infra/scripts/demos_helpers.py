"""Helpers for run_demos.py: DB lookups, dispatch, polling, snapshot save."""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DEMOS_DIR = REPO_ROOT / "demos"

POLL_INTERVAL_SECONDS = 30
# Match TIER_TIMEOUTS["large"] = 43200 (12h) — anything beyond that means
# the workflow itself has timed out. The old 4h cap printed exit-1
# TIMEOUTs on perfectly healthy large sims that legitimately ran 4-5h
# (e.g. sim 150 at 4h17min on 2026-05-15), and Temporal continued the
# workflow regardless so the script's exit code was just misleading.
MAX_WAIT_SECONDS = 12 * 60 * 60
DEMO_USER_EMAIL = "demo@fishcloud.internal"
TERMINAL_STATUSES = {"COMPLETED", "FAILED", "REFUNDED"}


def async_database_url() -> str:
    raw = os.getenv("DATABASE_URL", "")
    if not raw:
        print("ERROR: DATABASE_URL not set")
        sys.exit(1)
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql+psycopg2://"):
        return raw.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


async def get_or_create_demo_user(session) -> str:
    import bcrypt
    from sqlalchemy import text

    row = (
        await session.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": DEMO_USER_EMAIL},
        )
    ).first()
    if row:
        return str(row[0])

    pw_hash = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt()).decode()
    result = await session.execute(
        text(
            "INSERT INTO users (email, password_hash, email_verified, created_at) "
            "VALUES (:email, :pw, true, now()) RETURNING id"
        ),
        {"email": DEMO_USER_EMAIL, "pw": pw_hash},
    )
    user_id = str(result.scalar())
    await session.commit()
    print(f"  Created demo user: id={user_id}")
    return user_id


async def load_routing(session, tier: str):
    from sqlalchemy import select

    from saas.jobs.models import ModelRouting

    result = await session.execute(select(ModelRouting).where(ModelRouting.sim_tier == tier))
    routing = result.scalar_one_or_none()
    if not routing:
        raise RuntimeError(f"No model_routing row for tier={tier}; run seed migrations.")
    return routing


def build_storage():
    from saas.config import Settings
    from saas.storage.minio_client import SimDataStorage

    s = Settings()
    return SimDataStorage(
        endpoint=s.MINIO_ENDPOINT, access_key=s.MINIO_ACCESS_KEY,
        secret_key=s.MINIO_SECRET_KEY, bucket=s.MINIO_BUCKET,
        secure=s.MINIO_SECURE, proxy_base=s.MINIO_PROXY_BASE,
    )


async def dispatch_demo(session, temporal_client, storage, config, seed_text, dry_run=False):
    """Insert a SimulationJob row, start a SimulationWorkflow, return job_id (or None)."""
    from saas.jobs.models import JobStatus, SimulationJob
    from saas.workflows.client import SIM_TASK_QUEUE
    from saas.workflows.sim_workflow import SimulationWorkflow
    from saas.workflows.types import SimParams

    slug = config["slug"]
    tier = config["tier"]
    routing = await load_routing(session, tier)

    print(f"\n{'=' * 60}")
    print(f"Demo: {slug}")
    print(f"Goal: {config['goal']}")
    print(f"Tier: {tier} | Model: {routing.model_id} | GPU: {routing.gpu_type}")
    print(f"Seed: {len(seed_text)} chars")
    print(f"{'=' * 60}")

    if dry_run:
        print("  [DRY RUN] Would dispatch SimulationWorkflow")
        return None

    user_id = await get_or_create_demo_user(session)

    job = SimulationJob(
        user_id=user_id, seed_text=seed_text, goal=config["goal"], tier=tier,
        credits_charged=0, status=JobStatus.PENDING, enrich_web=True,
    )
    session.add(job)
    await session.flush()
    job_id = job.id

    upload_urls = storage.generate_upload_urls(job_id=job_id) if storage else None

    sim_params = SimParams(
        job_id=job_id, user_id=user_id, seed_text=seed_text, goal=config["goal"],
        tier=tier, model_id=routing.model_id, gpu_type=routing.gpu_type,
        max_rounds=routing.max_rounds, vllm_args=routing.vllm_args or "",
        llm_api_key=os.getenv("LLM_API_KEY", "not-needed"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        credits_charged=0, enrich_web=True, forecast_days=None,
        target_agents=routing.target_agents, upload_urls=upload_urls,
    )

    handle = await temporal_client.start_workflow(
        SimulationWorkflow.run, sim_params,
        id=f"sim-{job_id}", task_queue=SIM_TASK_QUEUE,
    )
    job.workflow_id = handle.id
    job.workflow_run_id = handle.result_run_id
    await session.commit()

    print(f"  Dispatched: job_id={job_id}, workflow_id={handle.id}")
    return job_id


async def wait_for_job(session_factory, job_id: int, slug: str):
    """Poll simulation_jobs.status until terminal. Returns dict of result fields on success."""
    from sqlalchemy import text

    start = asyncio.get_event_loop().time()
    last_status = None
    while asyncio.get_event_loop().time() - start < MAX_WAIT_SECONDS:
        async with session_factory() as session:
            row = (await session.execute(
                text(
                    "SELECT status, result_report, result_chat_log, result_graph, "
                    "result_structured, error_message FROM simulation_jobs WHERE id = :id"
                ),
                {"id": job_id},
            )).first()
        if row is None:
            print(f"  ERROR: job {job_id} disappeared")
            return None

        status, report, chat_log, graph, structured, error = row
        status_str = status.value if hasattr(status, "value") else str(status)
        if status_str != last_status:
            elapsed = int(asyncio.get_event_loop().time() - start)
            print(f"  [{elapsed}s] {slug}: status={status_str}", flush=True)
            last_status = status_str

        if status_str in TERMINAL_STATUSES:
            if status_str == "COMPLETED":
                return {
                    "report": report or "", "chat_log": chat_log or "[]",
                    "graph": graph or "{}", "structured": structured or "",
                }
            print(f"  FAILED: {error or status_str}")
            return None

        await asyncio.sleep(POLL_INTERVAL_SECONDS)

    print(f"  TIMEOUT after {MAX_WAIT_SECONDS}s")
    return None


def save_snapshot(config, result) -> Path:
    chat_log = result.get("chat_log", "[]")
    graph = result.get("graph", "{}")
    snapshot = {
        "slug": config["slug"], "title": config["title"],
        "description": config["description"], "seed_summary": config["seed_summary"],
        "goal": config["goal"], "tier": config["tier"],
        "agent_count": 0, "rounds": 0,
        "report_markdown": result.get("report", ""),
        "chat_log": json.loads(chat_log) if isinstance(chat_log, str) else chat_log,
        "graph_data": json.loads(graph) if isinstance(graph, str) else graph,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    DEMOS_DIR.mkdir(exist_ok=True)
    out = DEMOS_DIR / f"{config['slug']}.json"
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
