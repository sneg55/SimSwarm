"""Centralized tier configuration — single source of truth."""

TIER_CREDITS = {"small": 30, "medium": 90, "large": 300}
TIER_TIMEOUTS = {"small": 2700, "medium": 18000, "large": 43200}
TIER_MAX_COST_USD = {"small": 3.50, "medium": 4.00, "large": 8.00}
VALID_TIERS = frozenset(TIER_CREDITS.keys())

# Wall-clock cap applied inside generate_report_task's own tool loop,
# independent of the GPU-tier timeout (which no longer covers report gen).
TIER_REPORT_TIMEOUT_S = {"small": 300, "medium": 600, "large": 900}

# Round-progress watchdog. If poll_until_complete sees no advance in the
# max observed `round=N` value for this long, the sim is declared stuck
# and the activity fails so the workflow ends + refund fires. Sized at
# ~5-6× typical per-round wall-clock so transient slow rounds don't trip
# it (small ≈ 50-80s/round on H100; medium/large ≈ 100-200s/round on L40S).
TIER_STUCK_THRESHOLD_S = {"small": 300, "medium": 600, "large": 900}
