from __future__ import annotations
import json, sys
from datetime import datetime, timezone
from pathlib import Path

DEMOS_DIR = Path(__file__).parent.parent.parent / "demos"
SEEDS_DIR = DEMOS_DIR / "seeds"

DEMO_CONFIGS = [
    # Curated set surfaced on the landing page. Keep small (6) — every demo is
    # an expensive sim run on a real GPU; add only when there's a clear gap.
    {
        "slug": "hormuz-crisis-oil-shock",
        "title": "Strait of Hormuz Closure: Global Energy Market Shock",
        "description": "Simulating 3,000 energy traders, OPEC officials, shipping executives, and government policymakers reacting to Iran closing the Strait of Hormuz.",
        "seed_summary": "Iran's IRGC Navy closes Strait of Hormuz, Brent crude hits $110/barrel. US extends ultimatum deadline to April 6.",
        "seed_file": "hormuz-crisis-oil-shock.txt",
        "goal": "Predict global energy market response, supply chain disruptions, and government interventions over 30 days as the Hormuz crisis unfolds",
        "tier": "large",
    },
    {
        "slug": "bitcoin-halving",
        "title": "Crypto Community Sentiment Post-Halving",
        "description": "Simulating 2,500 agents across crypto Twitter, Telegram, Reddit, and institutional desks following the Bitcoin block reward halving.",
        "seed_summary": "Bitcoin block 1,050,000 mined. Block reward drops from 3.125 BTC to 1.5625 BTC. Bitcoin price at $78,400 at halving.",
        "seed_file": "bitcoin-halving.txt",
        "goal": "Forecast crypto community sentiment and price narrative evolution in the 60 days following the Bitcoin halving",
        "tier": "large",
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
            tier = config.get("tier", "small")
            min_chars = {"small": 2000, "medium": 5000, "large": 8000}.get(tier, 2000)
            if report_len < min_chars:
                status = f"⚠ {report_len} chars (< {min_chars} min for {tier}), {chat_entries} entries ({generated})"
            else:
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
