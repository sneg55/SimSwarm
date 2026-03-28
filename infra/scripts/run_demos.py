#!/usr/bin/env python3
"""
Run demo simulations against the production FishCloud API.

Usage:
    # Run all 10 new demos
    python infra/scripts/run_demos.py --api-url https://your-domain.com --token YOUR_JWT

    # Run specific demos
    python infra/scripts/run_demos.py --api-url https://your-domain.com --token YOUR_JWT \
        --slugs hormuz-crisis-oil-shock openai-sora-shutdown epic-fortnite-collapse

    # List all demos and their status
    python infra/scripts/run_demos.py --list

    # Dry run (show what would be submitted)
    python infra/scripts/run_demos.py --api-url https://your-domain.com --token YOUR_JWT --dry-run

Flow:
    1. Reads seed text from demos/seeds/<slug>.txt
    2. POST /api/jobs to create the simulation job
    3. Polls GET /api/jobs/<id> until completed or failed
    4. Saves result to demos/<slug>.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).parent.parent.parent
DEMOS_DIR = REPO_ROOT / "demos"
SEEDS_DIR = DEMOS_DIR / "seeds"

# Import demo configs
sys.path.insert(0, str(Path(__file__).parent))
from refresh_demos import DEMO_CONFIGS, _load_seed_text


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


def submit_job(api_url: str, token: str, seed_text: str, goal: str, tier: str) -> dict:
    """Submit a simulation job and return the job response."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = httpx.post(
        f"{api_url}/api/jobs",
        json={"seed_text": seed_text, "goal": goal, "tier": tier},
        headers=headers,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def poll_job(api_url: str, token: str, job_id: int, poll_interval: int = 30, max_wait: int = 7200) -> dict:
    """Poll job status until completed or failed. Returns final job data."""
    headers = {"Authorization": f"Bearer {token}"}
    start = time.time()

    while time.time() - start < max_wait:
        resp = httpx.get(f"{api_url}/api/jobs/{job_id}", headers=headers, timeout=15)
        resp.raise_for_status()
        job = resp.json()
        status = job.get("status", "UNKNOWN")
        elapsed = int(time.time() - start)
        stage = job.get("pipeline_stage", "?")

        print(f"  [{elapsed}s] Job {job_id}: status={status} stage={stage}", flush=True)

        if status in ("COMPLETED", "FAILED", "REFUNDED"):
            return job

        time.sleep(poll_interval)

    raise TimeoutError(f"Job {job_id} did not complete within {max_wait}s")


def fetch_graph(api_url: str, token: str, job_id: int) -> dict | None:
    """Fetch graph data for a completed job."""
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = httpx.get(f"{api_url}/api/jobs/{job_id}/graph", headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def save_demo_snapshot(config: dict, job: dict, graph: dict | None) -> Path:
    """Save the completed job as a demo JSON snapshot."""
    snapshot = {
        "slug": config["slug"],
        "title": config["title"],
        "description": config["description"],
        "seed_summary": config["seed_summary"],
        "goal": config["goal"],
        "tier": config["tier"],
        "agent_count": job.get("pipeline_stage", 0),
        "rounds": 0,
        "report_markdown": job.get("result_report", ""),
        "chat_log": json.loads(job.get("result_chat_log", "[]")),
        "graph_data": graph or json.loads(job.get("result_graph", "{}")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "job_id": job.get("id"),
        "provision_seconds": job.get("provision_seconds"),
        "pipeline_seconds": job.get("pipeline_seconds"),
    }

    out_path = DEMOS_DIR / f"{config['slug']}.json"
    out_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def run_demo(config: dict, api_url: str, token: str, dry_run: bool = False) -> bool:
    """Run a single demo simulation. Returns True on success."""
    slug = config["slug"]
    seed_text = _load_seed_text(config)

    if not seed_text or seed_text == config.get("seed_summary", ""):
        seed_file = config.get("seed_file", "")
        if seed_file:
            print(f"  WARNING: Seed file {seed_file} not found, using seed_summary")

    print(f"\n{'='*60}")
    print(f"Demo: {slug}")
    print(f"Goal: {config['goal']}")
    print(f"Tier: {config['tier']} | Seed: {len(seed_text)} chars")
    print(f"{'='*60}")

    if dry_run:
        print("  [DRY RUN] Would submit job with above config")
        return True

    try:
        # Submit job
        job = submit_job(api_url, token, seed_text, config["goal"], config["tier"])
        job_id = job["id"]
        print(f"  Job created: id={job_id}, credits_charged={job.get('credits_charged')}")

        # Poll until complete
        final_job = poll_job(api_url, token, job_id)
        status = final_job.get("status")

        if status == "COMPLETED":
            report_len = len(final_job.get("result_report", ""))
            print(f"  COMPLETED: report={report_len} chars")

            # Fetch graph data
            graph = fetch_graph(api_url, token, job_id)
            if graph:
                nodes = len(graph.get("nodes", []))
                edges = len(graph.get("edges", []))
                print(f"  Graph: {nodes} nodes, {edges} edges")

            # Save snapshot
            out_path = save_demo_snapshot(config, final_job, graph)
            print(f"  Saved: {out_path}")
            return True
        else:
            error = final_job.get("error_message", "unknown")
            print(f"  FAILED: {error}")
            return False

    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run demo simulations against production API")
    parser.add_argument("--api-url", help="API base URL (e.g. https://fishcloud.example.com)")
    parser.add_argument("--token", help="JWT auth token")
    parser.add_argument("--slugs", nargs="*", help="Specific demo slugs to run (default: all new)")
    parser.add_argument("--all", action="store_true", help="Run all 15 demos (including original 5)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be submitted")
    parser.add_argument("--list", action="store_true", help="List all demos and their status")
    args = parser.parse_args()

    if args.list:
        from refresh_demos import list_demos
        list_demos()
        return

    if not args.api_url or not args.token:
        parser.error("--api-url and --token are required (unless using --list)")

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

    print(f"Running {len(configs)} demo simulations against {args.api_url}")
    print(f"Demos: {', '.join(c['slug'] for c in configs)}")

    results = {}
    for config in configs:
        success = run_demo(config, args.api_url, args.token, dry_run=args.dry_run)
        results[config["slug"]] = "OK" if success else "FAILED"

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for slug, status in results.items():
        print(f"  {slug}: {status}")

    ok = sum(1 for s in results.values() if s == "OK")
    print(f"\n{ok}/{len(results)} succeeded")

    if ok < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
