"""LLM error-rate circuit breaker in poll_until_complete.

When vLLM on a pod degrades, every llm.chat call hits TimeoutError,
the pipeline retries 3× per call and moves on, and rounds barely
advance. The stuck-watchdog eventually catches it at minutes-scale,
but if we trip a faster signal on error-line rate we can swap pods
and salvage 5-15 min of grind. This test suite locks in the
detection behavior; the actual swap lives in sim_workflow.py and is
covered separately.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.constants.tiers import (
    LLM_CIRCUIT_BREAKER_ERROR_RATE,
    LLM_CIRCUIT_BREAKER_MARKER,
    LLM_CIRCUIT_BREAKER_MIN_SAMPLES,
)
from saas.jobs import pipeline


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("saas.jobs.pipeline.asyncio.sleep", new_callable=AsyncMock):
        yield


def _completed_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {
        "status": "completed", "report": "r", "chat_log": "[]",
        "graph_data": "{}", "structured": "{}", "sim_data_uploaded": True,
    }
    return r


def _running_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"status": "running"}
    return r


def _partial_chat_response():
    pc = MagicMock()
    pc.status_code = 200
    pc.json.return_value = {"messages": []}
    return pc


def _logs_response(lines: list[str]):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"lines": lines}
    return r


class _Cfg:
    def __init__(self, tier: str = "medium"):
        self.job_id = 1
        self.tier = tier
        self.timeout_seconds = 99999
        self.max_rounds = 200


def _make_client(status_seq, logs_seq):
    """Cycle through status_seq for /status and logs_seq for /logs."""
    state = {"s_i": 0, "l_i": 0}

    def side(url, **kw):
        if "/partial_chat" in url:
            return _partial_chat_response()
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


async def test_does_not_trip_on_zero_errors():
    """Clean pipeline logs → no circuit breaker even if /logs is polled."""
    healthy_logs = [
        "round=1/200",
        "round=2/200",
        "round=3/200",
    ]
    status_seq = [_running_response(), _running_response(), _completed_response()]
    logs_seq = [_logs_response(healthy_logs)] * 10
    client = _make_client(status_seq, logs_seq)

    with patch("saas.jobs.pipeline._update_live_status_sync"):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(), client=client,
        )
    assert result["status"] == "completed"


async def test_does_not_trip_below_min_sample_size():
    """A few errors but tiny sample → no trip. We need MIN_SAMPLES total
    LLM-relevant lines before evaluating the rate; otherwise a fresh pod
    with one unlucky log batch could false-positive."""
    # Only 3 error lines, no successful llm.chat lines → 3 errors / 3 total = 100%
    # but below MIN_SAMPLES threshold.
    assert LLM_CIRCUIT_BREAKER_MIN_SAMPLES > 3, (
        "test assumes MIN_SAMPLES > 3 so a tiny error burst doesn't trip"
    )
    short_errors = [
        "round=1/200",
        "llm.chat transient error attempt=1/3: TimeoutError — retrying in 1.0s",
        "llm.chat transient error attempt=1/3: TimeoutError — retrying in 1.0s",
        "llm.chat transient error attempt=1/3: TimeoutError — retrying in 1.0s",
    ]
    status_seq = [_running_response(), _completed_response()]
    logs_seq = [_logs_response(short_errors), _logs_response(short_errors)]
    client = _make_client(status_seq, logs_seq)

    with patch("saas.jobs.pipeline._update_live_status_sync"):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(), client=client,
        )
    assert result["status"] == "completed"


async def test_trips_when_error_rate_exceeds_threshold():
    """Many transient errors, no successful work → trip with the marker."""
    # 18 error lines, 2 round= lines → 18/20 = 90% > 0.7
    flood = [
        "llm.chat transient error attempt=1/3: TimeoutError — retrying in 1.0s",
    ] * 18 + ["round=5/200", "round=5/200"]
    # Each /logs poll returns the same flood (worst case sustained).
    status_seq = [_running_response()] * 50
    logs_seq = [_logs_response(flood)] * 50
    client = _make_client(status_seq, logs_seq)

    assert LLM_CIRCUIT_BREAKER_ERROR_RATE < 0.9, "test assumes 90% > threshold"

    with patch("saas.jobs.pipeline._update_live_status_sync"):
        with pytest.raises(Exception) as excinfo:
            await pipeline.poll_until_complete(
                "http://w", "pod1", _Cfg(), client=client,
            )
    assert LLM_CIRCUIT_BREAKER_MARKER in str(excinfo.value)


async def test_does_not_trip_on_low_baseline_error_rate():
    """A normal pipeline gets the occasional transient error mixed with
    plenty of real progress (20% errors). That must NOT trip the breaker
    — only sustained dominance should fire."""
    # Each /logs batch: 4 errors + 16 round= lines where the round number
    # also advances across batches so the stuck-watchdog doesn't fire.
    def mixed_batch(start: int) -> list[str]:
        return (
            ["llm.chat transient error attempt=1/3: TimeoutError"] * 4
            + [f"round={start + i}/200" for i in range(16)]
        )

    status_seq = [_running_response()] * 30 + [_completed_response()]
    logs_seq = [_logs_response(mixed_batch(i * 16)) for i in range(40)]
    client = _make_client(status_seq, logs_seq)

    assert 4 / 20 < LLM_CIRCUIT_BREAKER_ERROR_RATE, (
        "test assumes baseline 20% < threshold"
    )

    with patch("saas.jobs.pipeline._update_live_status_sync"), \
            patch(
                "saas.jobs.pipeline.time.monotonic",
                side_effect=[i * 30 for i in range(10000)],
            ):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(), client=client,
        )
    assert result["status"] == "completed"
