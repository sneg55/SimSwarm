# Plan 6: Benchmarking

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and run the benchmarking suite that validates credit pricing yields >= 60% gross margin. This is a pre-launch gate — no launch without passing benchmarks.

**Architecture:** A Python benchmarking script that runs 3 simulations per tier on actual GPU infrastructure, measures COGS (GPU-hours, tokens, wall-clock time), and generates a pricing validation report.

**Tech Stack:** Python, pytest, RunPod SDK, JSON reporting

**Depends on:** Plan 3 (GPU orchestration, job runner)

**Spec reference:** `docs/superpowers/specs/2026-03-26-mirofish-hosted-mvp-design.md` — Appendix A (Benchmarking Plan)

---

## File Structure

```
infra/
└── scripts/
    ├── benchmark.py              # Main benchmarking script
    └── benchmark_report.py       # Report generation from results
docs/
└── benchmarks/
    ├── results.json              # Raw benchmark results (auto-generated)
    └── pricing_validation.md     # Human-readable pricing report (auto-generated)
tests/
├── test_benchmark_script.py      # Benchmark script unit tests
└── test_benchmark_report.py      # Report generation tests
```

---

### Task 1: Benchmark Data Model + COGS Calculator

**Files:**
- Create: `infra/scripts/benchmark.py` (data models only)
- Create: `tests/test_benchmark_script.py`

- [ ] **Step 1: Write benchmark data model tests**

```python
# tests/test_benchmark_script.py
import pytest
from infra.scripts.benchmark import (
    BenchmarkRun,
    BenchmarkResult,
    TierBenchmark,
    calculate_cogs,
    calculate_margin,
    CREDIT_PRICES_USD,
)


def test_credit_prices_defined():
    assert CREDIT_PRICES_USD["small"] == pytest.approx(5.70)   # 30 credits * $0.19
    assert CREDIT_PRICES_USD["medium"] == pytest.approx(14.22)  # 90 credits * ($19/100)
    assert CREDIT_PRICES_USD["large"] == pytest.approx(37.35)   # 300 credits * ($249/2000)


def test_calculate_cogs():
    run = BenchmarkRun(
        tier="small",
        gpu_type="a100-40gb",
        gpu_cost_per_hour_usd=1.50,
        gpu_hours=0.45,
        total_tokens=2_500_000,
        wall_clock_seconds=1620,
        total_rounds=50,
        total_agents=300,
        success=True,
    )
    cogs = calculate_cogs(run)
    # GPU cost: 0.45 * 1.50 = $0.675
    # No additional token cost (self-hosted vLLM)
    assert cogs == pytest.approx(0.675)


def test_calculate_margin():
    # Revenue per small sim: $5.70 (Starter pack: $19 / 100 credits * 30 credits)
    # COGS: $0.675
    margin = calculate_margin(revenue_usd=5.70, cogs_usd=0.675)
    assert margin == pytest.approx(88.16, rel=0.01)  # 88% margin


def test_margin_below_threshold():
    # If COGS is too high
    margin = calculate_margin(revenue_usd=5.70, cogs_usd=3.00)
    assert margin == pytest.approx(47.37, rel=0.01)  # Below 60% threshold


def test_tier_benchmark_average():
    runs = [
        BenchmarkRun(
            tier="small", gpu_type="a100-40gb", gpu_cost_per_hour_usd=1.50,
            gpu_hours=0.40, total_tokens=2_000_000, wall_clock_seconds=1500,
            total_rounds=50, total_agents=300, success=True,
        ),
        BenchmarkRun(
            tier="small", gpu_type="a100-40gb", gpu_cost_per_hour_usd=1.50,
            gpu_hours=0.50, total_tokens=3_000_000, wall_clock_seconds=1800,
            total_rounds=50, total_agents=300, success=True,
        ),
        BenchmarkRun(
            tier="small", gpu_type="a100-40gb", gpu_cost_per_hour_usd=1.50,
            gpu_hours=0.45, total_tokens=2_500_000, wall_clock_seconds=1620,
            total_rounds=50, total_agents=300, success=True,
        ),
    ]
    tb = TierBenchmark(tier="small", runs=runs)
    assert tb.avg_gpu_hours == pytest.approx(0.45)
    assert tb.avg_cogs_usd == pytest.approx(0.675)
    assert tb.success_rate == pytest.approx(1.0)


def test_tier_benchmark_with_failure():
    runs = [
        BenchmarkRun(
            tier="small", gpu_type="a100-40gb", gpu_cost_per_hour_usd=1.50,
            gpu_hours=0.40, total_tokens=2_000_000, wall_clock_seconds=1500,
            total_rounds=50, total_agents=300, success=True,
        ),
        BenchmarkRun(
            tier="small", gpu_type="a100-40gb", gpu_cost_per_hour_usd=1.50,
            gpu_hours=0.10, total_tokens=500_000, wall_clock_seconds=600,
            total_rounds=10, total_agents=300, success=False,
        ),
    ]
    tb = TierBenchmark(tier="small", runs=runs)
    assert tb.success_rate == pytest.approx(0.5)
    # Average COGS only from successful runs
    assert tb.avg_cogs_usd == pytest.approx(0.60)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_benchmark_script.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement benchmark data models**

```python
# infra/scripts/benchmark.py
"""
MiroFish Hosted COGS Benchmarking Suite.

Runs simulations per tier, measures GPU cost, and validates pricing.

Usage:
  python -m infra.scripts.benchmark --tier small --runs 3
  python -m infra.scripts.benchmark --all --runs 3
  python -m infra.scripts.benchmark --all --runs 3 --dry-run
"""
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BENCHMARKS_DIR = Path(__file__).parent.parent.parent / "docs" / "benchmarks"

# Revenue per sim = pack_price / pack_credits * tier_credits
# Using weighted average across packs:
# Starter: $19/100 = $0.19/credit
# Pro: $79/500 = $0.158/credit
# Heavy: $249/2000 = $0.1245/credit
# Use Starter pricing (worst case for margin):
CREDIT_PRICE_PER_UNIT = 0.19  # $/credit (Starter pack rate)

TIER_CREDITS = {"small": 30, "medium": 90, "large": 300}

CREDIT_PRICES_USD = {
    tier: credits * CREDIT_PRICE_PER_UNIT
    for tier, credits in TIER_CREDITS.items()
}


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
        if not self.runs:
            return 0.0
        return len(self.successful_runs) / len(self.runs)

    @property
    def avg_gpu_hours(self) -> float:
        successful = self.successful_runs
        if not successful:
            return 0.0
        return sum(r.gpu_hours for r in successful) / len(successful)

    @property
    def avg_cogs_usd(self) -> float:
        successful = self.successful_runs
        if not successful:
            return 0.0
        return sum(calculate_cogs(r) for r in successful) / len(successful)

    @property
    def avg_wall_clock_seconds(self) -> float:
        successful = self.successful_runs
        if not successful:
            return 0.0
        return sum(r.wall_clock_seconds for r in successful) / len(successful)


@dataclass
class BenchmarkResult:
    tiers: dict[str, TierBenchmark]
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "tiers": {
                tier: {
                    "runs": [
                        {
                            "gpu_type": r.gpu_type,
                            "gpu_cost_per_hour_usd": r.gpu_cost_per_hour_usd,
                            "gpu_hours": r.gpu_hours,
                            "total_tokens": r.total_tokens,
                            "wall_clock_seconds": r.wall_clock_seconds,
                            "total_rounds": r.total_rounds,
                            "total_agents": r.total_agents,
                            "success": r.success,
                            "error": r.error,
                            "cogs_usd": calculate_cogs(r),
                            "timestamp": r.timestamp,
                        }
                        for r in tb.runs
                    ],
                    "avg_gpu_hours": tb.avg_gpu_hours,
                    "avg_cogs_usd": tb.avg_cogs_usd,
                    "avg_wall_clock_seconds": tb.avg_wall_clock_seconds,
                    "success_rate": tb.success_rate,
                    "revenue_usd": CREDIT_PRICES_USD[tier],
                    "margin_pct": calculate_margin(
                        CREDIT_PRICES_USD[tier], tb.avg_cogs_usd
                    ),
                }
                for tier, tb in self.tiers.items()
            },
        }


def calculate_cogs(run: BenchmarkRun) -> float:
    """Calculate cost of goods sold for a single run.
    COGS = GPU hours * GPU cost/hour (self-hosted vLLM = no per-token cost)."""
    return run.gpu_hours * run.gpu_cost_per_hour_usd


def calculate_margin(revenue_usd: float, cogs_usd: float) -> float:
    """Calculate gross margin percentage."""
    if revenue_usd == 0:
        return 0.0
    return ((revenue_usd - cogs_usd) / revenue_usd) * 100


# --- Execution ---

TIER_CONFIGS = {
    "small": {"agents": 300, "rounds": 50, "gpu_type": "a100-40gb"},
    "medium": {"agents": 1000, "rounds": 100, "gpu_type": "h100-80gb"},
    "large": {"agents": 5000, "rounds": 150, "gpu_type": "h100-80gb"},
}


def run_benchmark(tier: str, num_runs: int = 3, dry_run: bool = False) -> TierBenchmark:
    """Run benchmark simulations for a given tier."""
    config = TIER_CONFIGS[tier]
    runs = []

    for i in range(num_runs):
        print(f"  Run {i+1}/{num_runs} for {tier} tier...")

        if dry_run:
            # Simulated dry-run result
            run = BenchmarkRun(
                tier=tier,
                gpu_type=config["gpu_type"],
                gpu_cost_per_hour_usd=1.50 if "a100" in config["gpu_type"] else 3.50,
                gpu_hours=0.45 if tier == "small" else (2.0 if tier == "medium" else 8.0),
                total_tokens=2_500_000 if tier == "small" else (10_000_000 if tier == "medium" else 50_000_000),
                wall_clock_seconds=1620 if tier == "small" else (7200 if tier == "medium" else 28800),
                total_rounds=config["rounds"],
                total_agents=config["agents"],
                success=True,
            )
        else:
            # Real execution via job runner
            run = _execute_benchmark_run(tier, config)

        runs.append(run)
        print(f"    COGS: ${calculate_cogs(run):.2f} | Wall-clock: {run.wall_clock_seconds}s | Success: {run.success}")

    return TierBenchmark(tier=tier, runs=runs)


def _execute_benchmark_run(tier: str, config: dict) -> BenchmarkRun:
    """Execute a real benchmark run using the GPU orchestration layer."""
    import asyncio
    import os
    from saas.gpu.runpod_provider import RunPodProvider
    from saas.workers.job_runner import JobRunner, JobConfig

    gpu = RunPodProvider(api_key=os.getenv("RUNPOD_API_KEY", ""))
    runner = JobRunner(gpu_provider=gpu)

    job_config = JobConfig(
        job_id=0,  # benchmark, no real job
        user_id="benchmark",
        seed_text="Benchmark seed: AI regulation news for testing purposes.",
        goal="Benchmark: predict industry response (test run)",
        tier=tier,
        model_id=os.getenv("BENCHMARK_MODEL", "Qwen2.5-32B-Instruct-AWQ"),
        gpu_type=config["gpu_type"],
        max_rounds=config["rounds"],
        vllm_args="--quantization awq --max-model-len 32768",
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        zep_api_key=os.getenv("ZEP_API_KEY", ""),
    )

    start_time = time.time()
    try:
        result = asyncio.run(runner.run(job_config))
        elapsed = time.time() - start_time
        return BenchmarkRun(
            tier=tier,
            gpu_type=config["gpu_type"],
            gpu_cost_per_hour_usd=1.50 if "a100" in config["gpu_type"] else 3.50,
            gpu_hours=elapsed / 3600,
            total_tokens=0,  # TODO: capture from vLLM metrics
            wall_clock_seconds=int(elapsed),
            total_rounds=config["rounds"],
            total_agents=config["agents"],
            success=True,
        )
    except Exception as e:
        elapsed = time.time() - start_time
        return BenchmarkRun(
            tier=tier,
            gpu_type=config["gpu_type"],
            gpu_cost_per_hour_usd=1.50 if "a100" in config["gpu_type"] else 3.50,
            gpu_hours=elapsed / 3600,
            total_tokens=0,
            wall_clock_seconds=int(elapsed),
            total_rounds=0,
            total_agents=0,
            success=False,
            error=str(e),
        )


def run_all_benchmarks(num_runs: int = 3, dry_run: bool = False) -> BenchmarkResult:
    """Run benchmarks for all tiers and generate results."""
    tiers = {}
    for tier in ["small", "medium", "large"]:
        print(f"\nBenchmarking {tier} tier:")
        tiers[tier] = run_benchmark(tier, num_runs=num_runs, dry_run=dry_run)

    result = BenchmarkResult(tiers=tiers)

    # Save results
    BENCHMARKS_DIR.mkdir(parents=True, exist_ok=True)
    results_file = BENCHMARKS_DIR / "results.json"
    results_file.write_text(json.dumps(result.to_dict(), indent=2))
    print(f"\nResults saved to {results_file}")

    # Print summary
    print("\n=== PRICING VALIDATION ===")
    all_pass = True
    for tier, tb in tiers.items():
        revenue = CREDIT_PRICES_USD[tier]
        margin = calculate_margin(revenue, tb.avg_cogs_usd)
        status = "PASS" if margin >= 60 else "FAIL"
        if margin < 60:
            all_pass = False
        print(f"  {tier}: Revenue ${revenue:.2f} | COGS ${tb.avg_cogs_usd:.2f} | Margin {margin:.1f}% [{status}]")

    if all_pass:
        print("\nAll tiers PASS >= 60% margin. Ready for launch.")
    else:
        print("\nSome tiers FAIL. Adjust credit consumption per tier before launch.")

    return result


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    num_runs = 3
    for i, arg in enumerate(sys.argv):
        if arg == "--runs" and i + 1 < len(sys.argv):
            num_runs = int(sys.argv[i + 1])

    if "--tier" in sys.argv:
        tier_idx = sys.argv.index("--tier") + 1
        tier = sys.argv[tier_idx]
        result = run_benchmark(tier, num_runs=num_runs, dry_run=dry_run)
        print(f"\n{tier} avg COGS: ${result.avg_cogs_usd:.2f}, margin: {calculate_margin(CREDIT_PRICES_USD[tier], result.avg_cogs_usd):.1f}%")
    else:
        run_all_benchmarks(num_runs=num_runs, dry_run=dry_run)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_benchmark_script.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add infra/scripts/benchmark.py tests/test_benchmark_script.py
git commit -m "feat: add COGS benchmarking suite with margin validation"
```

---

### Task 2: Benchmark Report Generator

**Files:**
- Create: `infra/scripts/benchmark_report.py`
- Create: `tests/test_benchmark_report.py`

- [ ] **Step 1: Write report generator tests**

```python
# tests/test_benchmark_report.py
import pytest
from infra.scripts.benchmark_report import generate_markdown_report


def test_report_contains_all_tiers():
    results = {
        "generated_at": "2026-03-26T00:00:00Z",
        "tiers": {
            "small": {
                "avg_gpu_hours": 0.45,
                "avg_cogs_usd": 0.675,
                "avg_wall_clock_seconds": 1620,
                "success_rate": 1.0,
                "revenue_usd": 5.70,
                "margin_pct": 88.16,
                "runs": [],
            },
            "medium": {
                "avg_gpu_hours": 2.0,
                "avg_cogs_usd": 7.00,
                "avg_wall_clock_seconds": 7200,
                "success_rate": 1.0,
                "revenue_usd": 17.10,
                "margin_pct": 59.06,
                "runs": [],
            },
            "large": {
                "avg_gpu_hours": 8.0,
                "avg_cogs_usd": 28.00,
                "avg_wall_clock_seconds": 28800,
                "success_rate": 0.67,
                "revenue_usd": 57.00,
                "margin_pct": 50.88,
                "runs": [],
            },
        },
    }
    report = generate_markdown_report(results)
    assert "small" in report.lower()
    assert "medium" in report.lower()
    assert "large" in report.lower()
    assert "88.1" in report or "88.2" in report  # small margin
    assert "FAIL" in report  # large tier fails 60% threshold


def test_report_has_recommendation():
    results = {
        "generated_at": "2026-03-26T00:00:00Z",
        "tiers": {
            "small": {
                "avg_gpu_hours": 0.45, "avg_cogs_usd": 0.675,
                "avg_wall_clock_seconds": 1620, "success_rate": 1.0,
                "revenue_usd": 5.70, "margin_pct": 88.16, "runs": [],
            },
        },
    }
    report = generate_markdown_report(results)
    assert "Recommendation" in report or "recommendation" in report
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_benchmark_report.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement report generator**

```python
# infra/scripts/benchmark_report.py
"""
Generate a human-readable pricing validation report from benchmark results.

Usage: python -m infra.scripts.benchmark_report
"""
from __future__ import annotations

import json
from pathlib import Path

BENCHMARKS_DIR = Path(__file__).parent.parent.parent / "docs" / "benchmarks"
MARGIN_THRESHOLD = 60.0


def generate_markdown_report(results: dict) -> str:
    lines = [
        "# MiroFish Hosted — Pricing Validation Report",
        "",
        f"**Generated:** {results['generated_at']}",
        "",
        "## Summary",
        "",
        "| Tier | Revenue | Avg COGS | Margin | Status |",
        "|------|---------|----------|--------|--------|",
    ]

    all_pass = True
    failing_tiers = []

    for tier, data in results["tiers"].items():
        margin = data["margin_pct"]
        status = "PASS" if margin >= MARGIN_THRESHOLD else "FAIL"
        if margin < MARGIN_THRESHOLD:
            all_pass = False
            failing_tiers.append(tier)

        lines.append(
            f"| {tier} | ${data['revenue_usd']:.2f} | ${data['avg_cogs_usd']:.2f} "
            f"| {margin:.1f}% | {status} |"
        )

    lines.extend(["", "## Performance", ""])
    lines.append("| Tier | Avg GPU Hours | Avg Wall Clock | Success Rate |")
    lines.append("|------|---------------|----------------|--------------|")

    for tier, data in results["tiers"].items():
        wc_min = data["avg_wall_clock_seconds"] / 60
        lines.append(
            f"| {tier} | {data['avg_gpu_hours']:.2f}h "
            f"| {wc_min:.0f} min | {data['success_rate']*100:.0f}% |"
        )

    lines.extend(["", "## Recommendation", ""])

    if all_pass:
        lines.append(
            "All tiers meet the >= 60% gross margin threshold. "
            "**Credit pricing is validated. Ready for launch.**"
        )
    else:
        lines.append(
            f"The following tiers FAIL the 60% margin threshold: **{', '.join(failing_tiers)}**."
        )
        lines.append("")
        lines.append("**Action required before launch:**")
        lines.append("")
        for tier in failing_tiers:
            data = results["tiers"][tier]
            # Calculate minimum credits needed for 60% margin
            min_revenue = data["avg_cogs_usd"] / 0.40  # 60% margin = COGS is 40% of revenue
            min_credits = min_revenue / 0.19  # At Starter pack rate
            lines.append(
                f"- **{tier}**: Increase credit consumption from current level "
                f"to at least **{int(min_credits) + 1} credits** per sim, "
                f"OR reduce COGS below ${data['revenue_usd'] * 0.40:.2f}"
            )

    lines.append("")
    return "\n".join(lines)


def main():
    results_file = BENCHMARKS_DIR / "results.json"
    if not results_file.exists():
        print("No benchmark results found. Run benchmark.py first.")
        return

    results = json.loads(results_file.read_text())
    report = generate_markdown_report(results)

    output_file = BENCHMARKS_DIR / "pricing_validation.md"
    output_file.write_text(report)
    print(f"Report written to {output_file}")
    print(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_benchmark_report.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run dry-run benchmark to generate sample output**

```bash
python -m infra.scripts.benchmark --all --runs 3 --dry-run
python -m infra.scripts.benchmark_report
```

Expected: Generates `docs/benchmarks/results.json` and `docs/benchmarks/pricing_validation.md` with simulated data.

- [ ] **Step 6: Commit**

```bash
git add infra/scripts/benchmark_report.py tests/test_benchmark_report.py docs/benchmarks/
git commit -m "feat: add benchmark report generator with pricing validation"
```

---

### Task 3: Benchmark Integration with CI

**Files:**
- Create: `tests/test_benchmark_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_benchmark_integration.py
"""
Integration test: run dry-run benchmarks and verify the full pipeline
from execution through report generation.
"""
import json
import pytest
from pathlib import Path
from infra.scripts.benchmark import run_all_benchmarks, CREDIT_PRICES_USD, calculate_margin
from infra.scripts.benchmark_report import generate_markdown_report


def test_dry_run_benchmark_pipeline(tmp_path, monkeypatch):
    # Point output to tmp dir
    monkeypatch.setattr(
        "infra.scripts.benchmark.BENCHMARKS_DIR", tmp_path
    )

    result = run_all_benchmarks(num_runs=2, dry_run=True)

    # Verify results file was created
    results_file = tmp_path / "results.json"
    assert results_file.exists()

    # Verify all tiers present
    data = json.loads(results_file.read_text())
    assert "small" in data["tiers"]
    assert "medium" in data["tiers"]
    assert "large" in data["tiers"]

    # Verify each tier has expected runs
    for tier in ["small", "medium", "large"]:
        tier_data = data["tiers"][tier]
        assert len(tier_data["runs"]) == 2
        assert tier_data["success_rate"] == 1.0
        assert tier_data["avg_cogs_usd"] > 0

    # Generate report from results
    report = generate_markdown_report(data)
    assert "Pricing Validation Report" in report
    assert "Recommendation" in report


def test_dry_run_margins_are_positive():
    result = run_all_benchmarks(num_runs=1, dry_run=True)

    for tier, tb in result.tiers.items():
        revenue = CREDIT_PRICES_USD[tier]
        margin = calculate_margin(revenue, tb.avg_cogs_usd)
        # Dry-run values should yield positive margins
        assert margin > 0, f"{tier} has negative margin: {margin}%"
```

- [ ] **Step 2: Run integration test**

```bash
pytest tests/test_benchmark_integration.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_benchmark_integration.py
git commit -m "feat: add benchmark integration tests with dry-run pipeline validation"
```

---

## Test Suite Summary (After Plan 6)

| File | Tests | What it covers |
|------|-------|----------------|
| `test_benchmark_script.py` | 7 | COGS calculation, margin, tier averages, failure handling |
| `test_benchmark_report.py` | 2 | Report content, recommendations |
| `test_benchmark_integration.py` | 2 | Full dry-run pipeline, margin positivity |
| **Plan 6 Total** | **11** | |
| *(Plans 1-5)* | 92 | |
| **Grand Total** | **103** | |

---

## Pre-Launch Checklist

After all 6 plans are implemented:

1. Run `pytest -v` — all 103 tests must pass
2. Run `python -m infra.scripts.benchmark --all --runs 3` (with real GPUs) — validates pricing
3. Review `docs/benchmarks/pricing_validation.md` — all tiers must show >= 60% margin
4. If any tier fails margin check: adjust `TIER_CREDITS` in `saas/billing/credit_packs.py` and re-run
5. Run `python -m infra.scripts.refresh_demos` — generates demo content
6. Deploy and verify end-to-end: sign up -> buy credits -> run sim -> see results
