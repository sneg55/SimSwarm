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

# LLM error-rate circuit breaker. Sampled inside poll_until_complete on
# every /logs fetch. Trips when sustained errors dominate the pipeline —
# usually means vLLM on this pod has degraded and retries are looping
# forever. The workflow catches the marker and swaps pods once. Sized to
# fire well before the stuck-watchdog so we salvage time when a pod swap
# can still help.
LLM_CIRCUIT_BREAKER_WINDOW_S = 60         # rolling window
LLM_CIRCUIT_BREAKER_ERROR_RATE = 0.7      # errors / total > this trips
LLM_CIRCUIT_BREAKER_MIN_SAMPLES = 10      # don't trip on small samples
LLM_CIRCUIT_BREAKER_MARKER = "llm_circuit_broken"  # marker for workflow retry

# RunPod cloud pool selection per tier. "ALL" lets RunPod pick the
# cheapest pod from community + secure; "SECURE" restricts to vetted
# datacenter hosts. Large sims live with this for 2-3h so wall-clock
# variance is the dominant cost driver — paying ~2× hourly for SECURE
# eliminates the long-tail 8h+ runs we'd otherwise see on community.
# Small/medium runs are short enough that cost matters more than tail
# latency.
TIER_CLOUD_TYPE = {"small": "ALL", "medium": "ALL", "large": "SECURE"}

# Pod-unreachable marker + tolerance. When temporal-worker can't reach
# the pod's /status endpoint for MAX_CONSECUTIVE_POLL_FAILURES polls
# (× 10s poll interval = 5min), poll_until_complete raises with this
# marker. The workflow catches it and retries submit_and_poll once
# — the activity is idempotent: it checks /status on re-entry and
# resumes polling if the pod is still running or completed. Sim 149
# (2026-05-15) lost a near-completed bitcoin run to a 50s proxy blip
# on the old 5-failure threshold; 30 raises tolerance to 5min before
# the workflow even sees the marker.
MAX_CONSECUTIVE_POLL_FAILURES = 30
POD_UNREACHABLE_MARKER = "pod_unreachable"
