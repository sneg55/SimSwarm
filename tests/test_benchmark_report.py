"""
Tests for infra/scripts/benchmark_report.py — Task 2 (2 tests)
"""

from infra.scripts.benchmark_report import generate_markdown_report


def _make_results(
    small_margin: float = 88.0,
    medium_margin: float = 75.0,
    large_margin: float = 65.0,
) -> dict:
    """Build a minimal results dict compatible with generate_markdown_report."""
    return {
        "generated_at": "2026-01-01T00:00:00+00:00",
        "dry_run": True,
        "num_runs": 3,
        "tiers": {
            "small": {
                "revenue_usd": 5.70,
                "avg_cogs_usd": 5.70 * (1 - small_margin / 100),
                "margin_pct": small_margin,
                "avg_gpu_hours": 0.30,
                "avg_wall_clock_seconds": 180.0,
                "success_rate": 1.0,
            },
            "medium": {
                "revenue_usd": 17.10,
                "avg_cogs_usd": 17.10 * (1 - medium_margin / 100),
                "margin_pct": medium_margin,
                "avg_gpu_hours": 0.80,
                "avg_wall_clock_seconds": 600.0,
                "success_rate": 1.0,
            },
            "large": {
                "revenue_usd": 57.00,
                "avg_cogs_usd": 57.00 * (1 - large_margin / 100),
                "margin_pct": large_margin,
                "avg_gpu_hours": 2.00,
                "avg_wall_clock_seconds": 1800.0,
                "success_rate": 0.9,
            },
        },
    }


# ---------------------------------------------------------------------------
# Test 1: report contains all tiers and shows FAIL for below-threshold
# ---------------------------------------------------------------------------

def test_report_contains_all_tiers_and_fail_status():
    """
    Report must include a row for each tier. Any tier whose margin is below
    MARGIN_THRESHOLD must show FAIL; tiers above the threshold show PASS.
    """
    # Large tier at 55 % is below 60 % threshold → should be FAIL
    results = _make_results(small_margin=88.0, medium_margin=75.0, large_margin=55.0)
    report = generate_markdown_report(results)

    # All three tier names appear in the report
    assert "Small" in report or "small" in report
    assert "Medium" in report or "medium" in report
    assert "Large" in report or "large" in report

    # The below-threshold tier shows FAIL
    assert "FAIL" in report

    # The above-threshold tiers show PASS
    assert "PASS" in report

    # Verify that large (55 %) is labelled FAIL while small/medium are PASS
    # We check order in the table: Large row comes after Small and Medium rows
    large_section = report[report.lower().index("large"):]
    assert "FAIL" in large_section


# ---------------------------------------------------------------------------
# Test 2: report has a recommendation section
# ---------------------------------------------------------------------------

def test_report_has_recommendation_section():
    """
    The report must include a '## Recommendation' section.
    When all tiers pass it should indicate readiness for launch.
    When a tier fails it should suggest credit adjustments.
    """
    # All-pass scenario
    results_pass = _make_results(small_margin=88.0, medium_margin=75.0, large_margin=65.0)
    report_pass = generate_markdown_report(results_pass)
    assert "## Recommendation" in report_pass
    assert "ready for launch" in report_pass.lower() or "launch" in report_pass.lower()

    # Failing scenario
    results_fail = _make_results(small_margin=88.0, medium_margin=40.0, large_margin=55.0)
    report_fail = generate_markdown_report(results_fail)
    assert "## Recommendation" in report_fail
    # Should mention credit price or allocation adjustment
    assert (
        "credit" in report_fail.lower()
        or "adjust" in report_fail.lower()
        or "increase" in report_fail.lower()
    )
