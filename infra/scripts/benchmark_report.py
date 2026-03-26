"""
FishCloud Benchmark Report Generator
Produces a Markdown report from benchmark results and validates pricing margins.
"""
from __future__ import annotations

from infra.scripts.benchmark import CREDIT_PRICES_USD, calculate_margin

MARGIN_THRESHOLD = 60.0  # percent — minimum acceptable gross margin for launch


def _status(margin_pct: float) -> str:
    return "PASS" if margin_pct >= MARGIN_THRESHOLD else "FAIL"


def generate_markdown_report(results: dict) -> str:
    """
    Generate a Markdown report from the dict returned by ``run_all_benchmarks``.

    The report contains:
    - A summary table with Tier | Revenue | Avg COGS | Margin | Status
    - A performance table with Tier | Avg GPU Hours | Avg Wall Clock | Success Rate
    - A recommendation section indicating launch readiness
    """
    lines: list[str] = []

    generated_at = results.get("generated_at", "unknown")
    dry_run = results.get("dry_run", False)
    num_runs = results.get("num_runs", "?")

    lines.append("# FishCloud Benchmark Report")
    lines.append("")
    lines.append(f"**Generated:** {generated_at}  ")
    lines.append(f"**Mode:** {'dry-run (simulated)' if dry_run else 'live'}  ")
    lines.append(f"**Runs per tier:** {num_runs}")
    lines.append("")

    # ------------------------------------------------------------------
    # Summary table
    # ------------------------------------------------------------------
    lines.append("## Pricing & Margin Summary")
    lines.append("")
    lines.append("| Tier | Revenue (USD) | Avg COGS (USD) | Margin (%) | Status |")
    lines.append("|------|--------------|----------------|-----------|--------|")

    tiers_data = results.get("tiers", {})
    all_pass = True
    failing_tiers: list[str] = []

    for tier in ("small", "medium", "large"):
        if tier not in tiers_data:
            continue
        td = tiers_data[tier]
        revenue = td.get("revenue_usd", CREDIT_PRICES_USD.get(tier, 0))
        avg_cogs = td.get("avg_cogs_usd", 0)
        margin = td.get("margin_pct", calculate_margin(revenue, avg_cogs))
        status = _status(margin)
        if status == "FAIL":
            all_pass = False
            failing_tiers.append(tier)
        lines.append(
            f"| {tier.capitalize()} | ${revenue:.2f} | ${avg_cogs:.4f} | {margin:.2f}% | **{status}** |"
        )

    lines.append("")

    # ------------------------------------------------------------------
    # Performance table
    # ------------------------------------------------------------------
    lines.append("## Performance Metrics")
    lines.append("")
    lines.append("| Tier | Avg GPU Hours | Avg Wall Clock (s) | Success Rate |")
    lines.append("|------|--------------|-------------------|-------------|")

    for tier in ("small", "medium", "large"):
        if tier not in tiers_data:
            continue
        td = tiers_data[tier]
        avg_gpu_h = td.get("avg_gpu_hours", 0)
        avg_wc = td.get("avg_wall_clock_seconds", 0)
        sr = td.get("success_rate", 0)
        lines.append(
            f"| {tier.capitalize()} | {avg_gpu_h:.4f} | {avg_wc:.1f} | {sr * 100:.1f}% |"
        )

    lines.append("")

    # ------------------------------------------------------------------
    # Recommendation
    # ------------------------------------------------------------------
    lines.append("## Recommendation")
    lines.append("")
    if all_pass:
        lines.append(
            "All tiers meet the minimum margin threshold "
            f"({MARGIN_THRESHOLD:.0f}%). **The service is ready for launch.**"
        )
    else:
        failing_str = ", ".join(t.capitalize() for t in failing_tiers)
        lines.append(
            f"The following tier(s) fall below the {MARGIN_THRESHOLD:.0f}% margin threshold: "
            f"**{failing_str}**."
        )
        lines.append("")
        lines.append("Suggested actions:")
        for tier in failing_tiers:
            td = tiers_data.get(tier, {})
            avg_cogs = td.get("avg_cogs_usd", 0)
            # Minimum revenue needed for MARGIN_THRESHOLD
            min_revenue = avg_cogs / (1 - MARGIN_THRESHOLD / 100) if avg_cogs else 0
            current_credits = CREDIT_PRICES_USD.get(tier, 0)
            lines.append(
                f"- **{tier.capitalize()}**: current revenue ${current_credits:.2f}, "
                f"min required revenue for {MARGIN_THRESHOLD:.0f}% margin ≈ ${min_revenue:.2f}. "
                f"Consider increasing credit price or reducing GPU allocation."
            )

    lines.append("")
    return "\n".join(lines)
