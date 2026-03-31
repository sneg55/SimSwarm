#!/usr/bin/env python3
"""
Run demo simulations directly on the production server via Celery.

Meant to be run ON the server (SSH or docker exec) — dispatches tasks
directly to the Celery worker, bypassing auth and billing.

Usage (on server):
    cd /opt/fishcloud

    # Run all 10 new demos
    python infra/scripts/run_demos.py

    # Run specific demos
    python infra/scripts/run_demos.py --slugs hormuz-crisis-oil-shock openai-sora-shutdown

    # Run all 15 (including original 5)
    python infra/scripts/run_demos.py --all

    # List demo status
    python infra/scripts/run_demos.py --list

    # Dry run
    python infra/scripts/run_demos.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DEMOS_DIR = REPO_ROOT / "demos"

MIN_REPORT_CHARS = {"small": 2000, "medium": 5000, "large": 8000}
MAX_RETRIES = 2

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from refresh_demos import DEMO_CONFIGS, _load_seed_text

# Model routing defaults (match seed_model_routing_defaults.py migration)
TIER_ROUTING = {
    "small": {
        "model_id": "Qwen/Qwen2.5-32B-Instruct-AWQ",
        "gpu_type": "a100-40gb",
        "max_rounds": 200,
        "vllm_args": "--quantization awq --max-model-len 32768",
    },
    "medium": {
        "model_id": "Qwen/Qwen2.5-32B-Instruct-AWQ",
        "gpu_type": "h100-80gb",
        "max_rounds": 200,
        "vllm_args": "--quantization awq --max-model-len 32768",
    },
    "large": {
        "model_id": "Qwen/Qwen2.5-32B-Instruct-AWQ",
        "gpu_type": "h100-80gb",
        "max_rounds": 200,
        "vllm_args": "--quantization awq --max-model-len 32768",
    },
}

NEW_DEMO_SLUGS = [
    "hormuz-crisis-oil-shock",
    "iran-ceasefire-scenarios",
    "nato-iraq-withdrawal",
    "oil-110-global-impact",
    "spr-iran-sanctions",
    "openai-sora-shutdown",
    "spider-man-billion-trailer",
    "laguardia-crash",
    "meta-google-child-addiction",
    "epic-fortnite-collapse",
]


def dispatch_demo(config: dict, dry_run: bool = False) -> str | None:
    """Dispatch a demo simulation via Celery. Returns task ID or None."""
    from saas.workers.tasks import run_simulation_task

    slug = config["slug"]
    tier = config["tier"]
    routing = TIER_ROUTING[tier]
    seed_text = _load_seed_text(config)

    print(f"\n{'='*60}")
    print(f"Demo: {slug}")
    print(f"Goal: {config['goal']}")
    print(f"Tier: {tier} | Model: {routing['model_id']} | GPU: {routing['gpu_type']}")
    print(f"Seed: {len(seed_text)} chars")
    print(f"{'='*60}")

    if dry_run:
        print("  [DRY RUN] Would dispatch Celery task")
        return "dry-run"

    # Dispatch directly — no job row, no credits, no auth
    # Use job_id=0 and user_id="demo" since this is an operator-initiated run
    # credits_charged=0 so no refund logic triggers on failure
    result = run_simulation_task.delay(
        job_id=0,
        user_id="demo",
        seed_text=seed_text,
        goal=config["goal"],
        tier=tier,
        model_id=routing["model_id"],
        gpu_type=routing["gpu_type"],
        max_rounds=routing["max_rounds"],
        vllm_args=routing["vllm_args"],
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD", ""),
        credits_charged=0,
    )

    print(f"  Dispatched: task_id={result.id}")
    return result.id


def wait_for_task(task_id: str, slug: str, poll_interval: int = 30, max_wait: int = 7200) -> dict | None:
    """Wait for a Celery task to complete. Returns result dict or None."""
    from celery.result import AsyncResult
    from saas.workers.celery_app import celery_app

    result = AsyncResult(task_id, app=celery_app)
    start = time.time()

    while time.time() - start < max_wait:
        if result.ready():
            if result.successful():
                data = result.result
                report_len = len(data.get("report", ""))
                print(f"  COMPLETED: report={report_len} chars")
                return data
            else:
                print(f"  FAILED: {result.result}")
                return None

        elapsed = int(time.time() - start)
        state = result.state
        print(f"  [{elapsed}s] {slug}: state={state}", flush=True)
        time.sleep(poll_interval)

    print(f"  TIMEOUT after {max_wait}s")
    return None


def save_snapshot(config: dict, result: dict) -> Path:
    """Save Celery task result as a demo JSON snapshot."""
    snapshot = {
        "slug": config["slug"],
        "title": config["title"],
        "description": config["description"],
        "seed_summary": config["seed_summary"],
        "goal": config["goal"],
        "tier": config["tier"],
        "agent_count": 0,
        "rounds": 0,
        "report_markdown": result.get("report", ""),
        "chat_log": json.loads(result.get("chat_log", "[]")) if isinstance(result.get("chat_log"), str) else result.get("chat_log", []),
        "graph_data": json.loads(result.get("graph_data", "{}")) if isinstance(result.get("graph_data"), str) else result.get("graph_data", {}),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    out = DEMOS_DIR / f"{config['slug']}.json"
    out.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def run_one(config: dict, dry_run: bool = False) -> bool:
    """Run a single demo end-to-end. Returns True on success."""
    for attempt in range(MAX_RETRIES + 1):
        task_id = dispatch_demo(config, dry_run=dry_run)
        if not task_id or dry_run:
            return dry_run

        result = wait_for_task(task_id, config["slug"])
        if not result:
            if attempt < MAX_RETRIES:
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} after failure...")
                continue
            return False

        report_len = len(result.get("report", ""))
        tier = config["tier"]
        min_chars = MIN_REPORT_CHARS.get(tier, 2000)

        if report_len < min_chars and attempt < MAX_RETRIES:
            print(f"  Report too short ({report_len} chars < {min_chars} min for {tier}). Retrying...")
            continue

        out = save_snapshot(config, result)
        print(f"  Saved: {out}")
        if report_len < min_chars:
            print(f"  WARNING: Report still short after {MAX_RETRIES} retries ({report_len} chars)")
        return True

    return False


def main():
    parser = argparse.ArgumentParser(description="Run demo simulations via Celery on the production server")
    parser.add_argument("--slugs", nargs="*", help="Specific demo slugs to run (default: 10 new)")
    parser.add_argument("--all", action="store_true", help="Run all 15 demos")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be dispatched")
    parser.add_argument("--list", action="store_true", help="List all demos and their status")
    parser.add_argument("--parallel", action="store_true", help="Dispatch all at once, then wait (faster but more GPUs)")
    args = parser.parse_args()

    if args.list:
        from refresh_demos import list_demos
        list_demos()
        return

    # Determine which demos to run
    if args.slugs:
        slugs = args.slugs
    elif args.all:
        slugs = [c["slug"] for c in DEMO_CONFIGS]
    else:
        slugs = NEW_DEMO_SLUGS

    configs = []
    for slug in slugs:
        config = next((c for c in DEMO_CONFIGS if c["slug"] == slug), None)
        if not config:
            print(f"Unknown demo slug: {slug}")
            sys.exit(1)
        configs.append(config)

    print(f"Running {len(configs)} demos")

    if args.parallel and not args.dry_run:
        # Dispatch all tasks first
        tasks = []
        for config in configs:
            task_id = dispatch_demo(config)
            if task_id:
                tasks.append((config, task_id))

        # Then wait for all results
        print(f"\nAll {len(tasks)} tasks dispatched. Waiting for results...\n")
        results = {}
        for config, task_id in tasks:
            data = wait_for_task(task_id, config["slug"])
            if data:
                out = save_snapshot(config, data)
                print(f"  Saved: {out}")
                results[config["slug"]] = "OK"
            else:
                results[config["slug"]] = "FAILED"
    else:
        # Sequential — one at a time
        results = {}
        for config in configs:
            ok = run_one(config, dry_run=args.dry_run)
            results[config["slug"]] = "OK" if ok else "FAILED"

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for slug, status in results.items():
        print(f"  {slug}: {status}")

    ok = sum(1 for s in results.values() if s == "OK")
    print(f"\n{ok}/{len(results)} succeeded")

    if ok < len(results) and not args.dry_run:
        sys.exit(1)


if __name__ == "__main__":
    main()
