"""
Tests for infra/scripts/benchmark.py — Task 1 (7 tests)
"""
import pytest

from infra.scripts.benchmark import (
    CREDIT_PRICES_USD,
    BenchmarkRun,
    TierBenchmark,
    calculate_cogs,
    calculate_margin,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(
    tier: str = "small",
    gpu_hours: float = 0.45,
    gpu_cost: float = 1.50,
    success: bool = True,
) -> BenchmarkRun:
    return BenchmarkRun(
        tier=tier,
        gpu_type="A100-40GB",
        gpu_cost_per_hour_usd=gpu_cost,
        gpu_hours=gpu_hours,
        total_tokens=10_000,
        wall_clock_seconds=120,
        total_rounds=2,
        total_agents=1,
        success=success,
    )


# ---------------------------------------------------------------------------
# Test 1: credit prices defined correctly
# ---------------------------------------------------------------------------

def test_credit_prices_small():
    """Small tier: 30 credits × $0.19 = $5.70"""
    assert abs(CREDIT_PRICES_USD["small"] - 5.70) < 0.001


def test_credit_prices_medium():
    """Medium tier: 90 credits × $0.19 = $17.10"""
    assert abs(CREDIT_PRICES_USD["medium"] - 17.10) < 0.01


def test_credit_prices_large():
    """Large tier: 300 credits × $0.19 = $57.00"""
    assert abs(CREDIT_PRICES_USD["large"] - 57.00) < 0.01


# ---------------------------------------------------------------------------
# Test 2: calculate_cogs
# ---------------------------------------------------------------------------

def test_calculate_cogs():
    """0.45 GPU-hours × $1.50/h = $0.675"""
    run = _make_run(gpu_hours=0.45, gpu_cost=1.50)
    assert abs(calculate_cogs(run) - 0.675) < 1e-9


# ---------------------------------------------------------------------------
# Test 3: calculate_margin
# ---------------------------------------------------------------------------

def test_calculate_margin_positive():
    """Revenue $5.70, COGS $0.675 => ~88.16 % margin"""
    margin = calculate_margin(revenue_usd=5.70, cogs_usd=0.675)
    assert abs(margin - 88.158) < 0.01


# ---------------------------------------------------------------------------
# Test 4: margin below threshold
# ---------------------------------------------------------------------------

def test_margin_below_threshold():
    """If COGS > revenue the margin should be negative (below 60 %)."""
    margin = calculate_margin(revenue_usd=1.00, cogs_usd=0.50)
    assert margin == 50.0
    # A margin of 50 % is below the 60 % launch threshold
    assert margin < 60.0


# ---------------------------------------------------------------------------
# Test 5: tier benchmark average
# ---------------------------------------------------------------------------

def test_tier_benchmark_avg_cogs():
    """avg_cogs_usd should be the mean of calculate_cogs across successful runs."""
    runs = [
        _make_run(gpu_hours=0.30, gpu_cost=1.50),  # COGS = 0.45
        _make_run(gpu_hours=0.60, gpu_cost=1.50),  # COGS = 0.90
    ]
    tb = TierBenchmark(tier="small", runs=runs)
    assert abs(tb.avg_cogs_usd - 0.675) < 1e-9


# ---------------------------------------------------------------------------
# Test 6: tier benchmark with failures
# ---------------------------------------------------------------------------

def test_tier_benchmark_with_failure():
    """Failed runs should be excluded from avg_cogs_usd and success_rate < 1."""
    runs = [
        _make_run(gpu_hours=0.30, gpu_cost=1.50, success=True),   # COGS = 0.45
        _make_run(gpu_hours=0.90, gpu_cost=1.50, success=False),  # excluded
    ]
    tb = TierBenchmark(tier="small", runs=runs)
    assert tb.success_rate == 0.5
    assert abs(tb.avg_cogs_usd - 0.45) < 1e-9


# ---------------------------------------------------------------------------
# Test 7: credit_prices dict is defined for all tiers
# ---------------------------------------------------------------------------

def test_credit_prices_all_tiers_defined():
    """CREDIT_PRICES_USD must contain entries for small, medium, and large."""
    assert set(CREDIT_PRICES_USD.keys()) == {"small", "medium", "large"}
