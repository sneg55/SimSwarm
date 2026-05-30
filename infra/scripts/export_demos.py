#!/usr/bin/env python3
"""
Export completed simulation results to demo JSON files.

Usage:
    python -m infra.scripts.export_demos

Maps job IDs to demo slugs and writes to demos/*.json
"""
import json
import re
import os
from datetime import datetime, timezone
from pathlib import Path

# Job ID → demo slug mapping (update these after running real sims)
JOB_DEMO_MAP = {
    35: "iran-war-us-china",
    36: "tesla-earnings",
    37: "dream-red-chamber",
    38: "eu-ai-act",
    39: "bitcoin-halving",
}

DEMO_METADATA = {
    "iran-war-us-china": {
        "title": "US vs China Public Opinion on Iran Escalation",
        "description": "Simulating 1,000 agents across US and Chinese social media to predict opinion shifts over 30 days",
        "seed_summary": "EU Parliament bans AI political ads. Google, Meta, OpenAI push back citing free speech.",
        "goal": "Predict how tech companies, regulators, and public opinion will evolve over 30 days",
        "tier": "small",
    },
    "tesla-earnings": {
        "title": "Market Sentiment After Tesla Q1 Earnings",
        "description": "Simulating retail investors, institutional analysts, and market makers reacting to Tesla's mixed Q1 2026 results",
        "seed_summary": "Tesla Q1 2026: Revenue beats at $25.2B, but deliveries miss at 410K units. Model 2 delayed. Stock drops 9%.",
        "goal": "Predict retail investor sentiment, institutional response, and market price movement over 30 days",
        "tier": "small",
    },
    "dream-red-chamber": {
        "title": "Predicting the Lost Ending of Dream of the Red Chamber",
        "description": "Literary scholar agents reconstruct the original lost ending based on narrative arcs from the first 80 chapters",
        "seed_summary": "Jia Baoyu torn between Daiyu and Baochai as the Jia family declines. Multiple marriages arranged, Daiyu's health worsens.",
        "goal": "Predict the original lost ending based on character trajectories and thematic patterns",
        "tier": "small",
    },
    "eu-ai-act": {
        "title": "Industry Reaction to EU AI Act Enforcement",
        "description": "Simulating tech executives, startup founders, researchers, and regulators responding to AI Act enforcement",
        "seed_summary": "EU AI Act enforcement begins. High-risk AI systems must comply. Fines up to 35M EUR or 7% of revenue.",
        "goal": "Predict how tech industry, startups, researchers, and regulators respond over 60 days",
        "tier": "small",
    },
    "bitcoin-halving": {
        "title": "Crypto Community Sentiment Post-Halving",
        "description": "Simulating crypto traders, miners, and analysts reacting to Bitcoin's fourth halving event",
        "seed_summary": "Bitcoin halving reduces block reward to 1.5625 BTC. Mining profitability drops. BTC at $95K.",
        "goal": "Predict crypto community sentiment, miner behavior, and BTC price expectations over 30 days",
        "tier": "small",
    },
}

DEMOS_DIR = Path(__file__).parent.parent.parent / "demos"


def extract_markdown_from_report(raw_report: str) -> str:
    """Extract the markdown content from the Report(...) string stored in DB."""
    # Try to find markdown_content field
    match = re.search(r"markdown_content='(.*?)(?:',\s*created_at=|'\)$)", raw_report, re.DOTALL)
    if match:
        md = match.group(1)
        # Unescape
        md = md.replace("\\'", "'").replace("\\n", "\n").replace("\\t", "\t")
        return md

    # Fallback: try to find sections content
    sections = re.findall(r"content='(.*?)'(?:,\s*subsections|\))", raw_report, re.DOTALL)
    if sections:
        parts = []
        for s in sections:
            s = s.replace("\\'", "'").replace("\\n", "\n")
            parts.append(s)
        return "\n\n---\n\n".join(parts)

    # Last resort: return as-is
    return raw_report[:5000]


def extract_chat_log(raw_chat: str) -> list:
    """Parse chat log JSON string."""
    try:
        if raw_chat.startswith("["):
            return json.loads(raw_chat)
        # Might be truncated
        return json.loads(raw_chat + "]")
    except (json.JSONDecodeError, TypeError):
        return []


def export_demo(job_id: int, slug: str, db_url: str):
    """Export a single job's results to a demo JSON file."""
    import psycopg2
    # Convert async URL to sync
    sync_url = db_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    conn = psycopg2.connect(sync_url)
    cur = conn.cursor()
    cur.execute(
        "SELECT result_report, result_chat_log, created_at, completed_at FROM simulation_jobs WHERE id = %s",
        (job_id,),
    )
    row = cur.fetchone()
    conn.close()

    if not row or not row[0]:
        print(f"  Job {job_id} ({slug}): no results yet, skipping")
        return False

    report_raw, chat_raw, created_at, completed_at = row
    metadata = DEMO_METADATA[slug]

    report_md = extract_markdown_from_report(report_raw)
    chat_log = extract_chat_log(chat_raw or "[]")

    demo = {
        "slug": slug,
        "title": metadata["title"],
        "description": metadata["description"],
        "seed_summary": metadata["seed_summary"],
        "goal": metadata["goal"],
        "tier": metadata["tier"],
        "agent_count": len(set(c.get("agent_name", c.get("agent_id", "")) for c in chat_log)) or 4,
        "rounds": max((c.get("round_num", 0) for c in chat_log), default=0),
        "report_markdown": report_md,
        "chat_log": chat_log[:50],  # Limit to 50 entries for demo
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    output_file = DEMOS_DIR / f"{slug}.json"
    output_file.write_text(json.dumps(demo, indent=2, ensure_ascii=False, default=str))
    print(f"  Job {job_id} ({slug}): exported {len(report_md)} chars report, {len(chat_log)} chat entries")
    return True


def main():
    db_url = os.getenv("DATABASE_URL", "postgresql://fishcloud:fishcloud@localhost:5432/fishcloud")

    print("Exporting demo content from completed simulations...")
    exported = 0
    for job_id, slug in JOB_DEMO_MAP.items():
        if export_demo(job_id, slug, db_url):
            exported += 1

    print(f"\nExported {exported}/{len(JOB_DEMO_MAP)} demos to {DEMOS_DIR}")


if __name__ == "__main__":
    main()
