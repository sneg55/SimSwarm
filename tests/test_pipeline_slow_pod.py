"""Slow-pod detector in poll_until_complete.

Closes the "rounds advancing but way too slow" gap: pods where round
counter is moving but well below the baseline rate trip neither the
watchdog (rounds *are* advancing) nor the LLM circuit breaker (errors
stay under 70%). Sim 148 (hormuz, SECURE L40S, 2026-05-15) ran at
0.25 r/min when baseline is ~1.0; without this detector it would have
taken 12h+ wall-clock burning credits.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.constants.tiers import (
    SLOW_POD_MARKER,
    SLOW_POD_MIN_ROUND_DELTA,
    TIER_MIN_ROUNDS_PER_MIN,
)
from saas.jobs import pipeline


@pytest.fixture(autouse=True)
def _no_sleep():
    # Patch asyncio.sleep so the poll loop doesn't actually wait, AND
    # patch asyncio.to_thread so the wrapped sync DB call resolves
    # synchronously without going through the executor (avoids extra
    # event-loop scheduling that throws off the monotonic mock's call
    # counts in these timing-sensitive tests).
    async def _direct_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    with patch("saas.jobs.pipeline.asyncio.sleep", new_callable=AsyncMock), \
            patch("saas.jobs.pipeline.asyncio.to_thread", side_effect=_direct_to_thread):
        yield


def _running():
    r = MagicMock(status_code=200)
    r.json.return_value = {"status": "running"}
    return r


def _completed():
    r = MagicMock(status_code=200)
    r.json.return_value = {
        "status": "completed", "report": "r", "chat_log": "[]",
        "graph_data": "{}", "structured": "{}", "sim_data_uploaded": True,
    }
    return r


def _logs(lines):
    r = MagicMock(status_code=200)
    r.json.return_value = {"lines": lines}
    return r


def _partial_chat():
    pc = MagicMock(status_code=200)
    pc.json.return_value = {"messages": []}
    return pc


class _Cfg:
    def __init__(self, tier: str = "large"):
        self.job_id = 1
        self.tier = tier
        self.timeout_seconds = 99999
        self.max_rounds = 200


def _make_client(status_seq, logs_seq):
    state = {"s_i": 0, "l_i": 0}

    def side(url, **kw):
        if "/partial_chat" in url:
            return _partial_chat()
        if "/logs" in url:
            idx = min(state["l_i"], len(logs_seq) - 1)
            state["l_i"] += 1
            return logs_seq[idx]
        idx = min(state["s_i"], len(status_seq) - 1)
        state["s_i"] += 1
        return status_seq[idx]

    client = AsyncMock()
    client.get.side_effect = side
    return client


async def test_trips_on_sustained_slow_rate():
    """Round delta over a long window such that rate is well below
    the tier threshold → marker raises before watchdog catches it."""
    n_status = 60
    status_seq = [_running() for _ in range(n_status)]
    logs_seq = [_logs([f"round={i}/200"]) for i in range(1, n_status + 1)]
    client = _make_client(status_seq, logs_seq)

    # Pipeline calls monotonic ~2× per /logs iteration and 1× per non-/logs.
    # With step=80, /logs samples land at now_mono = 80, 320, 560, 800,
    # 1040, 1280... — spacing 240s. 5 samples fit the 1200s window → delta=4
    # at iter 8, rate = 4/(1040-80)*60 ≈ 0.25 r/min, below medium threshold
    # 0.3 → trip.
    with patch("saas.jobs.pipeline._update_live_status_sync"), \
            patch(
                "saas.jobs.pipeline.time.monotonic",
                side_effect=[i * 80 for i in range(10000)],
            ):
        with pytest.raises(RuntimeError, match=SLOW_POD_MARKER):
            await pipeline.poll_until_complete(
                "http://w", "pod1", _Cfg(tier="medium"), client=client,
            )


async def test_does_not_trip_on_healthy_rate():
    """Round rate above tier threshold → completes cleanly."""
    # Large threshold 0.4 r/min. Healthy baseline ~1.0+ → simulate ~2 r/min.
    n_status = 20
    status_seq = [_running() for _ in range(n_status - 1)] + [_completed()]
    # 2× rounds per /logs (fired every other poll) → big round deltas
    logs_seq = [_logs([f"round={i * 4}/200"]) for i in range(1, n_status + 1)]
    client = _make_client(status_seq, logs_seq)

    # Each poll = 30s → /logs every 60s → 4 rounds / 60s = 4 r/min, well above 0.4
    with patch("saas.jobs.pipeline._update_live_status_sync"), \
            patch(
                "saas.jobs.pipeline.time.monotonic",
                side_effect=[i * 30 for i in range(10000)],
            ):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(tier="large"), client=client,
        )
    assert result["status"] == "completed"


async def test_does_not_trip_before_min_round_delta():
    """Only a couple of rounds in the window → not enough sample to judge,
    no false-fire during warmup."""
    # Only 3 unique rounds total — below SLOW_POD_MIN_ROUND_DELTA=5
    assert SLOW_POD_MIN_ROUND_DELTA > 3
    n_status = 6
    status_seq = [_running() for _ in range(n_status - 1)] + [_completed()]
    logs_seq = [_logs([f"round={i}/200"]) for i in [1, 2, 3, 3, 3, 3]]
    client = _make_client(status_seq, logs_seq)

    # Pathologically slow timing — but only 3 unique rounds, so gate blocks the check
    with patch("saas.jobs.pipeline._update_live_status_sync"), \
            patch(
                "saas.jobs.pipeline.time.monotonic",
                side_effect=[i * 200 for i in range(10000)],
            ):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(tier="large"), client=client,
        )
    assert result["status"] == "completed"


async def test_tier_threshold_honored():
    """Same observed rate that trips large should NOT trip small/medium
    if the thresholds differ. Rate sized between small/medium (0.3) and
    large (0.4) — completes on small, would trip on large."""
    assert TIER_MIN_ROUNDS_PER_MIN["large"] > TIER_MIN_ROUNDS_PER_MIN["small"]
    n_status = 25
    status_seq = [_running() for _ in range(n_status - 1)] + [_completed()]
    logs_seq = [_logs([f"round={i}/200"]) for i in range(1, n_status + 1)]
    client = _make_client(status_seq, logs_seq)

    # step=58 → /logs samples spaced ~174s → ~7 samples in 1200s window,
    # 6 advances/1044s ≈ 0.345 r/min — above small/medium 0.3 threshold.
    with patch("saas.jobs.pipeline._update_live_status_sync"), \
            patch(
                "saas.jobs.pipeline.time.monotonic",
                side_effect=[i * 58 for i in range(10000)],
            ):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(tier="small"), client=client,
        )
    assert result["status"] == "completed"
