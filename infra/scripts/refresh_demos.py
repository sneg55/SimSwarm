from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path

DEMOS_DIR = Path(__file__).parent.parent.parent / "demos"

DEMO_CONFIGS = [
    {
        "slug": "iran-war-us-china",
        "title": "US vs China Public Opinion on Iran Escalation",
        "description": "Simulating 1,000 agents across US and Chinese social media platforms to model diverging public opinion on Iran nuclear escalation.",
        "seed_summary": "Breaking: Iran nuclear talks collapse after IAEA inspectors denied access to Fordow facility.",
        "seed_source": "public-domain-news",
        "goal": "Predict US vs China public opinion on Iran escalation over 30 days",
        "tier": "medium",
    },
    {
        "slug": "tesla-earnings",
        "title": "Market Sentiment After Tesla Q1 Earnings",
        "description": "Simulating 800 agents including retail investors, institutional analysts, and short sellers following a major Tesla earnings miss.",
        "seed_summary": "Tesla Q1 2026 earnings: Revenue missed expectations by 12%, delivery numbers down 18% YoY.",
        "seed_source": "sec-10k-excerpt",
        "goal": "Forecast retail investor sentiment and trading behavior following Tesla Q1 earnings miss over 30 days",
        "tier": "medium",
    },
    {
        "slug": "dream-red-chamber",
        "title": "Predicting the Lost Ending of Dream of the Red Chamber",
        "description": "Simulating 200 literary agents to reconstruct the lost final chapters of Cao Xueqin's 18th-century Chinese masterpiece.",
        "seed_summary": "The original Dream of the Red Chamber exists only in its first 80 chapters. The final 40 chapters were completed posthumously by Gao E.",
        "seed_source": "gutenberg",
        "goal": "Reconstruct the most historically and stylistically authentic lost ending of Dream of the Red Chamber",
        "tier": "small",
    },
    {
        "slug": "eu-ai-act",
        "title": "Industry Reaction to EU AI Act Enforcement",
        "description": "Simulating 900 agents representing tech companies, EU regulators, and civil society to model compliance behavior under the EU AI Act.",
        "seed_summary": "The EU AI Act high-risk provisions formally take effect today. Companies using AI in hiring, credit scoring, and critical infrastructure must now demonstrate conformity assessments.",
        "seed_source": "public-policy-doc",
        "goal": "Forecast industry compliance behavior and regulatory friction during the first 90 days of EU AI Act enforcement",
        "tier": "medium",
    },
    {
        "slug": "bitcoin-halving",
        "title": "Crypto Community Sentiment Post-Halving",
        "description": "Simulating 1,200 agents across crypto Twitter, Telegram, Reddit, and institutional desks following the Bitcoin block reward halving.",
        "seed_summary": "Bitcoin block 1,050,000 mined. Block reward drops from 3.125 BTC to 1.5625 BTC. Bitcoin price at $78,400 at halving.",
        "seed_source": "crypto-news-roundup",
        "goal": "Forecast crypto community sentiment and price narrative evolution in the 60 days following the Bitcoin halving",
        "tier": "medium",
    },
]


def validate_snapshot(snapshot: dict) -> bool:
    required = {"slug", "report_markdown", "chat_log"}
    if not required.issubset(snapshot.keys()):
        return False
    if not snapshot.get("report_markdown", "").strip():
        return False
    return True


def generate_demo_snapshot(config: dict) -> dict:
    existing_file = DEMOS_DIR / f"{config['slug']}.json"
    if existing_file.exists():
        return json.loads(existing_file.read_text())
    return {
        "slug": config["slug"],
        "title": config["title"],
        "description": config["description"],
        "seed_summary": config["seed_summary"],
        "goal": config["goal"],
        "tier": config["tier"],
        "agent_count": 0,
        "rounds": 0,
        "report_markdown": "# Pending\n\nWaiting for first run.",
        "chat_log": [],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def refresh_all(dry_run=False):
    DEMOS_DIR.mkdir(exist_ok=True)
    for config in DEMO_CONFIGS:
        snapshot = generate_demo_snapshot(config)
        if not validate_snapshot(snapshot):
            continue
        snapshot["generated_at"] = datetime.now(timezone.utc).isoformat()
        if not dry_run:
            (DEMOS_DIR / f"{config['slug']}.json").write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False)
            )


if __name__ == "__main__":
    refresh_all(dry_run="--dry-run" in sys.argv)
