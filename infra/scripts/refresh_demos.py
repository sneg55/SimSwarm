from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path

DEMOS_DIR = Path(__file__).parent.parent.parent / "demos"
SEEDS_DIR = DEMOS_DIR / "seeds"

DEMO_CONFIGS = [
    # --- Original 5 ---
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
        "seed_file": "eu-ai-act.txt",
        "goal": "Forecast industry compliance behavior and regulatory friction during the first 90 days of EU AI Act enforcement",
        "tier": "medium",
    },
    {
        "slug": "bitcoin-halving",
        "title": "Crypto Community Sentiment Post-Halving",
        "description": "Simulating 1,200 agents across crypto Twitter, Telegram, Reddit, and institutional desks following the Bitcoin block reward halving.",
        "seed_summary": "Bitcoin block 1,050,000 mined. Block reward drops from 3.125 BTC to 1.5625 BTC. Bitcoin price at $78,400 at halving.",
        "seed_file": "bitcoin-halving.txt",
        "goal": "Forecast crypto community sentiment and price narrative evolution in the 60 days following the Bitcoin halving",
        "tier": "medium",
    },
    # --- New 10 (March 27, 2026) ---
    {
        "slug": "hormuz-crisis-oil-shock",
        "title": "Strait of Hormuz Closure: Global Energy Market Shock",
        "description": "Simulating energy traders, OPEC officials, shipping executives, and government policymakers reacting to Iran closing the Strait of Hormuz.",
        "seed_summary": "Iran's IRGC Navy closes Strait of Hormuz, Brent crude hits $110/barrel. US extends ultimatum deadline to April 6.",
        "seed_file": "hormuz-crisis-oil-shock.txt",
        "goal": "Predict global energy market response, supply chain disruptions, and government interventions over 30 days as the Hormuz crisis unfolds",
        "tier": "medium",
    },
    {
        "slug": "iran-ceasefire-scenarios",
        "title": "Iran War: Ceasefire Negotiation Scenarios",
        "description": "Simulating US, Iranian, and Pakistani diplomats, military officials, and regional actors modeling ceasefire negotiation outcomes.",
        "seed_summary": "US sends 15-point peace plan to Iran via Pakistan. Iran rejects initial proposal, sets 5 conditions. Trump extends ultimatum.",
        "seed_file": "iran-ceasefire-scenarios.txt",
        "goal": "Predict the three most likely outcomes of US-Iran ceasefire negotiations over the next 30 days and their probability",
        "tier": "medium",
    },
    {
        "slug": "nato-iraq-withdrawal",
        "title": "NATO Withdraws from Iraq: Power Vacuum Analysis",
        "description": "Simulating Iraqi militia commanders, ISIS remnants, Kurdish forces, and regional powers filling the security gap after NATO withdrawal.",
        "seed_summary": "NATO withdraws troops from Iraq. Islamic Resistance claims 27 strikes on US bases. PMF commanders killed in US airstrikes.",
        "seed_file": "nato-iraq-withdrawal.txt",
        "goal": "Predict the security and political power dynamics in Iraq over 60 days following NATO troop withdrawal",
        "tier": "medium",
    },
    {
        "slug": "oil-110-global-impact",
        "title": "$110 Oil: Which Economies Break First",
        "description": "Simulating energy ministers, central bankers, and consumers across 12 countries modeling cascading economic impacts of sustained high oil prices.",
        "seed_summary": "Brent at $110. Slovenia rations fuel. Philippines declares energy emergency. South Sudan imposes power cuts. Norway cuts fuel taxes.",
        "seed_file": "oil-110-global-impact.txt",
        "goal": "Predict which countries face energy crises, policy responses, and consumer behavior changes over 30 days at sustained $110+ oil",
        "tier": "medium",
    },
    {
        "slug": "spr-iran-sanctions",
        "title": "SPR Release + Iran Sanctions Relief: Market Reaction",
        "description": "Simulating oil traders, hedge funds, sovereign wealth funds, and energy analysts modeling the dual impact of SPR release and temporary sanctions relief.",
        "seed_summary": "US loans 45M barrels from SPR and lifts Iran oil sanctions for 30 days. Brent swings between $98-$110.",
        "seed_file": "spr-iran-sanctions.txt",
        "goal": "Predict oil price trajectory and market positioning ahead of the April 19 sanctions snapback deadline",
        "tier": "medium",
    },
    {
        "slug": "openai-sora-shutdown",
        "title": "OpenAI Kills Sora: Creator Ecosystem Fallout",
        "description": "Simulating AI creators, Disney executives, competing AI labs, and content agencies reacting to Sora's shutdown and the $1B Disney deal collapse.",
        "seed_summary": "OpenAI shuts down Sora. Disney's $1B IP licensing deal cancelled. Competitors Runway, Pika, Google Veo remain.",
        "seed_file": "openai-sora-shutdown.txt",
        "goal": "Predict creator migration patterns, competitor market share capture, and corporate AI content deal sentiment over 60 days",
        "tier": "medium",
    },
    {
        "slug": "spider-man-billion-trailer",
        "title": "Spider-Man: Brand New Day — Box Office Trajectory",
        "description": "Simulating moviegoers, theater chains, Disney investors, and entertainment analysts modeling the cultural and financial impact of the first 1B-view trailer.",
        "seed_summary": "Spider-Man: Brand New Day trailer hits 1 billion YouTube views in 7 days — first movie trailer ever to do so.",
        "seed_file": "spider-man-billion-trailer.txt",
        "goal": "Predict opening weekend box office, cultural impact trajectory, and MCU franchise revival narrative over 90 days",
        "tier": "small",
    },
    {
        "slug": "laguardia-crash",
        "title": "LaGuardia Air Canada Crash: Aviation Safety Response",
        "description": "Simulating FAA regulators, airline executives, pilots' unions, and airport operators modeling regulatory and operational changes after the runway collision.",
        "seed_summary": "Air Canada Express CRJ900 collides with firetruck at LaGuardia. Both pilots killed, 41 injured. NTSB investigating.",
        "seed_file": "laguardia-crash.txt",
        "goal": "Predict FAA regulatory response, airline industry operational changes, and public confidence impact over 60 days",
        "tier": "small",
    },
    {
        "slug": "meta-google-child-addiction",
        "title": "Meta & Google Liable for Child Addiction: Regulatory Cascade",
        "description": "Simulating tech lobbyists, state attorneys general, EU regulators, parent advocacy groups, and platform engineers modeling the regulatory and design response.",
        "seed_summary": "California jury rules Google and Meta liable for addicting a child to Instagram and YouTube. First successful verdict of its kind.",
        "seed_file": "meta-google-child-addiction.txt",
        "goal": "Predict the regulatory cascade, class action momentum, and platform design changes over 90 days following the landmark verdict",
        "tier": "medium",
    },
    {
        "slug": "epic-fortnite-collapse",
        "title": "Epic Games Layoffs: Gaming Industry Consolidation",
        "description": "Simulating game developers, Unreal Engine licensees, Fortnite creators, and indie studios modeling the ripple effects of Epic's 25% workforce cut.",
        "seed_summary": "Epic Games lays off 1,000+ employees and cuts $500M in spending amid sharp Fortnite player decline.",
        "seed_file": "epic-fortnite-collapse.txt",
        "goal": "Predict gaming industry consolidation, creator platform migration, and Unreal Engine ecosystem impact over 60 days",
        "tier": "small",
    },
]


def _load_seed_text(config: dict) -> str:
    """Load seed text from file if seed_file is specified, otherwise use seed_summary."""
    seed_file = config.get("seed_file")
    if seed_file:
        path = SEEDS_DIR / seed_file
        if path.exists():
            return path.read_text(encoding="utf-8")
    return config.get("seed_summary", "")


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


def get_config_by_slug(slug: str) -> dict | None:
    for config in DEMO_CONFIGS:
        if config["slug"] == slug:
            return config
    return None


def list_demos():
    """Print all configured demos with their status."""
    for config in DEMO_CONFIGS:
        slug = config["slug"]
        existing = DEMOS_DIR / f"{slug}.json"
        if existing.exists():
            data = json.loads(existing.read_text())
            report_len = len(data.get("report_markdown", ""))
            chat_entries = len(data.get("chat_log", []))
            generated = data.get("generated_at", "unknown")
            status = f"✓ {report_len} chars, {chat_entries} chat entries ({generated})"
        else:
            status = "✗ not generated"
        print(f"  {slug}: {status}")


if __name__ == "__main__":
    if "--list" in sys.argv:
        list_demos()
    elif "--dry-run" in sys.argv:
        refresh_all(dry_run=True)
    else:
        refresh_all(dry_run=False)
