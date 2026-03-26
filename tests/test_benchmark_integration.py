"""
Integration tests for the benchmark pipeline — Task 3 (2 tests)

These tests exercise run_all_benchmarks(dry_run=True) end-to-end, verifying
that results.json is written correctly and that all computed margins are positive.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from infra.scripts.benchmark import CREDIT_PRICES_USD, RESULTS_PATH, run_all_benchmarks


# ---------------------------------------------------------------------------
# Test 1: dry-run creates results.json with all tiers
# ---------------------------------------------------------------------------

def test_dry_run_benchmark_pipeline(tmp_path, monkeypatch):
    """
    run_all_benchmarks(dry_run=True) must:
    - return a dict with a 'tiers' key
    - contain all three tiers (small, medium, large)
    - write results.json to RESULTS_PATH (redirected to tmp_path in this test)
    """
    # Redirect output file to a temp location so we don't pollute the repo
    tmp_results = tmp_path / "results.json"
    monkeypatch.setattr(
        "infra.scripts.benchmark.RESULTS_PATH", tmp_results
    )

    results = run_all_benchmarks(num_runs=2, dry_run=True, seed=42)

    # Return value checks
    assert "tiers" in results
    assert set(results["tiers"].keys()) == {"small", "medium", "large"}
    assert results["dry_run"] is True

    # File was written
    assert tmp_results.exists(), "results.json was not created"

    persisted = json.loads(tmp_results.read_text())
    assert set(persisted["tiers"].keys()) == {"small", "medium", "large"}


# ---------------------------------------------------------------------------
# Test 2: dry-run margins are positive
# ---------------------------------------------------------------------------

def test_dry_run_margins_are_positive(tmp_path, monkeypatch):
    """
    For every tier in the dry-run output the computed margin must be > 0.
    This guards against regressions where COGS accidentally exceeds revenue.
    """
    tmp_results = tmp_path / "results.json"
    monkeypatch.setattr(
        "infra.scripts.benchmark.RESULTS_PATH", tmp_results
    )

    results = run_all_benchmarks(num_runs=3, dry_run=True, seed=99)

    for tier, td in results["tiers"].items():
        margin = td["margin_pct"]
        assert margin > 0, (
            f"Tier '{tier}' has non-positive margin: {margin:.2f}% "
            f"(avg_cogs={td['avg_cogs_usd']:.4f}, revenue={td['revenue_usd']:.2f})"
        )
