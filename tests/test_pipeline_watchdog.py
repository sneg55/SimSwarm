"""Round-progress watchdog for poll_until_complete.

Sims sometimes wedge mid-run (e.g. vLLM degrades, every llm.chat call hits
TimeoutError, pipeline keeps retrying forever). /status still reports
running, /logs keeps emitting the same round number, and without a
watchdog the temporal-worker happily polls for ~12 hours before the
poll budget runs out. Watchdog raises so the activity fails, the
workflow ends, and the user gets a refund instead of burning credits.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.constants.tiers import TIER_STUCK_THRESHOLD_S
from saas.jobs import pipeline


@pytest.fixture(autouse=True)
def _no_sleep():
    with patch("saas.jobs.pipeline.asyncio.sleep", new_callable=AsyncMock):
        yield


def _running_with_round(round_num: int):
    """Status response: pod still running."""
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"status": "running"}
    return r


def _logs_with_round(round_num: int):
    """Logs response containing a `round=N` line for _extract_live_status."""
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"lines": [f"round={round_num}/200"]}
    return r


def _completed_response():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {
        "status": "completed", "report": "r", "chat_log": "[]",
        "graph_data": "{}", "structured": "{}", "sim_data_uploaded": True,
    }
    return r


def _partial_chat_response():
    pc = MagicMock()
    pc.status_code = 200
    pc.json.return_value = {"messages": []}
    return pc


class _Cfg:
    def __init__(self, tier: str = "medium"):
        self.job_id = 1
        self.tier = tier
        self.timeout_seconds = 99999  # don't trip the unrelated max_polls cap
        self.max_rounds = 200


def _make_client(status_responses):
    """Build an AsyncClient mock whose /status calls cycle through
    `status_responses`, with /logs reusing the round number on each /status."""

    state = {"i": 0}

    def side(url, **kw):
        if "/partial_chat" in url:
            return _partial_chat_response()
        if "/logs" in url:
            # _logs are fetched every other poll; use the round attached
            # to whatever /status response we most recently returned
            return _logs_with_round(state.get("last_round", 0))
        # /status branch
        idx = min(state["i"], len(status_responses) - 1)
        state["i"] += 1
        resp, round_num = status_responses[idx]
        state["last_round"] = round_num
        return resp

    client = AsyncMock()
    client.get.side_effect = side
    return client


async def test_watchdog_does_not_fire_when_round_progresses():
    """Rounds advancing each poll → no stuckness raised → sim completes."""
    status_seq = [
        (_running_with_round(1), 1),
        (_running_with_round(2), 2),
        (_running_with_round(3), 3),
        (_completed_response(), 3),
    ]
    client = _make_client(status_seq)

    with patch("saas.jobs.pipeline._update_live_status_sync"), \
            patch("saas.jobs.pipeline.time.monotonic", side_effect=range(0, 10000, 30)):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(tier="medium"), client=client,
        )
    assert result["status"] == "completed"


async def test_watchdog_raises_when_round_stalled_past_threshold():
    """Round pinned at 5 for > medium threshold → RuntimeError ("stuck")."""
    # Stay on round=5 for every poll. Each poll advances monotonic clock by 30s.
    threshold = TIER_STUCK_THRESHOLD_S["medium"]
    n_polls = (threshold // 30) + 5  # past threshold
    status_seq = [(_running_with_round(5), 5) for _ in range(n_polls)]
    client = _make_client(status_seq)

    with patch("saas.jobs.pipeline._update_live_status_sync"), \
            patch(
                "saas.jobs.pipeline.time.monotonic",
                side_effect=[i * 30 for i in range(10000)],
            ):
        with pytest.raises(RuntimeError, match="stuck"):
            await pipeline.poll_until_complete(
                "http://w", "pod1", _Cfg(tier="medium"), client=client,
            )


async def test_watchdog_uses_tier_specific_threshold():
    """Large tier must let a sim sit longer than small before declaring stuck."""
    small_thresh = TIER_STUCK_THRESHOLD_S["small"]
    large_thresh = TIER_STUCK_THRESHOLD_S["large"]
    assert large_thresh > small_thresh, "large should tolerate longer stalls"

    # Stall just under small threshold — should NOT trip the large watchdog.
    n_polls = (small_thresh // 30) + 5
    status_seq = [(_running_with_round(7), 7) for _ in range(n_polls)]
    status_seq.append((_completed_response(), 7))
    client = _make_client(status_seq)

    with patch("saas.jobs.pipeline._update_live_status_sync"), \
            patch(
                "saas.jobs.pipeline.time.monotonic",
                side_effect=[i * 30 for i in range(10000)],
            ):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(tier="large"), client=client,
        )
    assert result["status"] == "completed"


async def test_watchdog_silent_before_first_round():
    """If the sim hasn't reported round=N yet (early provisioning / vLLM
    warmup), the watchdog must not false-fire even if /status loop runs
    longer than the stuck threshold."""
    threshold = TIER_STUCK_THRESHOLD_S["small"]
    n_polls = (threshold // 30) + 5

    # Status is "running" but logs have no round=N lines (round stays None).
    running = MagicMock()
    running.status_code = 200
    running.json.return_value = {"status": "running"}

    no_round_logs = MagicMock()
    no_round_logs.status_code = 200
    no_round_logs.json.return_value = {"lines": ["initializing agents..."]}

    completed = _completed_response()

    responses = [running] * n_polls + [completed]
    state = {"i": 0}

    def side(url, **kw):
        if "/partial_chat" in url:
            return _partial_chat_response()
        if "/logs" in url:
            return no_round_logs
        idx = min(state["i"], len(responses) - 1)
        state["i"] += 1
        return responses[idx]

    client = AsyncMock()
    client.get.side_effect = side

    with patch("saas.jobs.pipeline._update_live_status_sync"), \
            patch(
                "saas.jobs.pipeline.time.monotonic",
                side_effect=[i * 30 for i in range(10000)],
            ):
        result = await pipeline.poll_until_complete(
            "http://w", "pod1", _Cfg(tier="small"), client=client,
        )
    assert result["status"] == "completed"
