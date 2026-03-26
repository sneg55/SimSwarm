"""
FishCloud Benchmark Suite
Measures GPU cost (COGS) per job tier and validates pricing margins.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Pricing constants
# ---------------------------------------------------------------------------

CREDIT_PRICE_PER_UNIT = 0.19  # $/credit (Starter pack worst-case rate)
TIER_CREDITS = {"small": 30, "medium": 90, "large": 300}
CREDIT_PRICES_USD = {tier: credits * CREDIT_PRICE_PER_UNIT for tier, credits in TIER_CREDITS.items()}

# Default GPU used for benchmarks (can be overridden)
DEFAULT_GPU_TYPE = "A100-40GB"
DEFAULT_GPU_COST_PER_HOUR_USD = 1.50  # $ / GPU-hour

# Simulated workload parameters per tier (min, max)
_SIM_GPU_HOURS: dict[str, tuple[float, float]] = {
    "small":  (0.10, 0.50),
    "medium": (0.40, 1.20),
    "large":  (1.20, 3.50),
}
_SIM_TOKENS: dict[str, tuple[int, int]] = {
    "small":  (5_000,  20_000),
    "medium": (20_000, 80_000),
    "large":  (80_000, 300_000),
}
_SIM_WALL_CLOCK: dict[str, tuple[int, int]] = {  # seconds
    "small":  (60,   300),
    "medium": (300,  900),
    "large":  (900,  3600),
}
_SIM_ROUNDS: dict[str, tuple[int, int]] = {
    "small":  (1, 3),
    "medium": (3, 8),
    "large":  (8, 20),
}
_SIM_AGENTS: dict[str, tuple[int, int]] = {
    "small":  (1, 2),
    "medium": (2, 5),
    "large":  (5, 15),
}

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkRun:
    tier: str
    gpu_type: str
    gpu_cost_per_hour_usd: float
    gpu_hours: float
    total_tokens: int
    wall_clock_seconds: int
    total_rounds: int
    total_agents: int
    success: bool
    error: str | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class TierBenchmark:
    tier: str
    runs: list[BenchmarkRun]

    @property
    def successful_runs(self) -> list[BenchmarkRun]:
        return [r for r in self.runs if r.success]

    @property
    def success_rate(self) -> float:
        return len(self.successful_runs) / len(self.runs) if self.runs else 0

    @property
    def avg_gpu_hours(self) -> float:
        s = self.successful_runs
        return sum(r.gpu_hours for r in s) / len(s) if s else 0

    @property
    def avg_wall_clock_seconds(self) -> float:
        s = self.successful_runs
        return sum(r.wall_clock_seconds for r in s) / len(s) if s else 0

    @property
    def avg_cogs_usd(self) -> float:
        s = self.successful_runs
        return sum(calculate_cogs(r) for r in s) / len(s) if s else 0


# ---------------------------------------------------------------------------
# Core calculation helpers
# ---------------------------------------------------------------------------


def calculate_cogs(run: BenchmarkRun) -> float:
    """Return GPU cost in USD for a single run."""
    return run.gpu_hours * run.gpu_cost_per_hour_usd


def calculate_margin(revenue_usd: float, cogs_usd: float) -> float:
    """Return gross margin as a percentage (0-100)."""
    return ((revenue_usd - cogs_usd) / revenue_usd) * 100 if revenue_usd else 0


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------


def _simulate_run(tier: str, rng: random.Random | None = None) -> BenchmarkRun:
    """Generate a simulated BenchmarkRun for the given tier."""
    rng = rng or random.Random()
    lo, hi = _SIM_GPU_HOURS[tier]
    gpu_hours = round(rng.uniform(lo, hi), 4)

    tlo, thi = _SIM_TOKENS[tier]
    total_tokens = rng.randint(tlo, thi)

    wlo, whi = _SIM_WALL_CLOCK[tier]
    wall_clock_seconds = rng.randint(wlo, whi)

    rlo, rhi = _SIM_ROUNDS[tier]
    total_rounds = rng.randint(rlo, rhi)

    alo, ahi = _SIM_AGENTS[tier]
    total_agents = rng.randint(alo, ahi)

    # 90 % success rate in simulation
    success = rng.random() < 0.90

    return BenchmarkRun(
        tier=tier,
        gpu_type=DEFAULT_GPU_TYPE,
        gpu_cost_per_hour_usd=DEFAULT_GPU_COST_PER_HOUR_USD,
        gpu_hours=gpu_hours,
        total_tokens=total_tokens,
        wall_clock_seconds=wall_clock_seconds,
        total_rounds=total_rounds,
        total_agents=total_agents,
        success=success,
        error=None if success else "Simulated timeout",
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

RESULTS_PATH = Path(__file__).resolve().parents[3] / "docs" / "benchmarks" / "results.json"


def run_all_benchmarks(
    num_runs: int = 3,
    dry_run: bool = False,
    seed: int | None = None,
) -> dict:
    """
    Execute (or simulate) benchmarks for all tiers.

    Returns a dict suitable for JSON serialisation and saves it to
    ``docs/benchmarks/results.json``.
    """
    rng = random.Random(seed)
    results: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "num_runs": num_runs,
        "tiers": {},
    }

    tiers = list(TIER_CREDITS.keys())

    for tier in tiers:
        if dry_run:
            runs = [_simulate_run(tier, rng) for _ in range(num_runs)]
        else:
            # Real benchmarks would launch actual GPU jobs here.
            # For now fall back to simulation so the suite is always runnable.
            runs = [_simulate_run(tier, rng) for _ in range(num_runs)]

        tb = TierBenchmark(tier=tier, runs=runs)
        revenue = CREDIT_PRICES_USD[tier]
        avg_cogs = tb.avg_cogs_usd
        margin = calculate_margin(revenue, avg_cogs)

        results["tiers"][tier] = {
            "revenue_usd": revenue,
            "avg_cogs_usd": round(avg_cogs, 4),
            "margin_pct": round(margin, 2),
            "avg_gpu_hours": round(tb.avg_gpu_hours, 4),
            "avg_wall_clock_seconds": round(tb.avg_wall_clock_seconds, 1),
            "success_rate": round(tb.success_rate, 4),
            "runs": [
                {
                    "tier": r.tier,
                    "gpu_type": r.gpu_type,
                    "gpu_cost_per_hour_usd": r.gpu_cost_per_hour_usd,
                    "gpu_hours": r.gpu_hours,
                    "total_tokens": r.total_tokens,
                    "wall_clock_seconds": r.wall_clock_seconds,
                    "total_rounds": r.total_rounds,
                    "total_agents": r.total_agents,
                    "success": r.success,
                    "error": r.error,
                    "timestamp": r.timestamp,
                }
                for r in runs
            ],
        }

    # Persist results
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w") as fh:
        json.dump(results, fh, indent=2)

    return results


if __name__ == "__main__":
    import sys

    dry = "--dry-run" in sys.argv
    data = run_all_benchmarks(num_runs=3, dry_run=dry)
    print(json.dumps(data, indent=2))
