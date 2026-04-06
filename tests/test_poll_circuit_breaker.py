"""Tests for poll_until_complete circuit breaker on consecutive failures."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.jobs.pipeline import poll_until_complete


def _make_config(job_id=1, timeout_seconds=3600):
    return type("Cfg", (), {"job_id": job_id, "timeout_seconds": timeout_seconds})()


class TestPollCircuitBreaker:
    """Verify poller exits after consecutive failures."""

    @pytest.fixture(autouse=True)
    def _mock_sleep(self):
        with patch("saas.jobs.pipeline.asyncio.sleep", new_callable=AsyncMock):
            yield

    @pytest.mark.asyncio
    async def test_raises_after_consecutive_failures(self):
        """5 consecutive poll failures should raise RuntimeError."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("connection refused")

        config = _make_config()
        with pytest.raises(RuntimeError, match="consecutive poll failures"):
            await poll_until_complete(
                worker_url="https://pod-dead-5000.proxy.runpod.net",
                instance_id="pod-dead",
                config=config,
                client=mock_client,
            )

        # Should have tried exactly 5 times before giving up
        assert mock_client.get.call_count == 5

    @pytest.mark.asyncio
    async def test_resets_counter_on_success(self):
        """A successful poll resets the consecutive failure counter."""
        call_count = 0

        async def get_side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise Exception("temporary failure")
            resp = MagicMock()
            resp.json.return_value = {"status": "completed", "report": "ok", "chat_log": "[]"}
            return resp

        mock_client = AsyncMock()
        mock_client.get.side_effect = get_side_effect

        config = _make_config()
        result = await poll_until_complete(
            worker_url="https://pod-ok-5000.proxy.runpod.net",
            instance_id="pod-ok",
            config=config,
            client=mock_client,
        )

        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_does_not_trip_on_intermittent_failures(self):
        """Alternating success/failure should not trip the breaker."""
        call_count = 0

        async def get_side_effect(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "/logs" in url or "/partial_chat" in url:
                resp = MagicMock()
                resp.status_code = 200
                resp.json.return_value = {"lines": [], "total_lines": 0}
                return resp
            # Alternate: fail, succeed, fail, succeed, ... then complete
            if call_count % 2 == 1 and call_count < 8:
                raise Exception("intermittent")
            resp = MagicMock()
            if call_count >= 8:
                resp.json.return_value = {
                    "status": "completed", "report": "done", "chat_log": "[]",
                }
            else:
                resp.json.return_value = {"status": "running"}
            return resp

        mock_client = AsyncMock()
        mock_client.get.side_effect = get_side_effect

        config = _make_config()
        result = await poll_until_complete(
            worker_url="https://pod-flaky-5000.proxy.runpod.net",
            instance_id="pod-flaky",
            config=config,
            client=mock_client,
        )

        assert result["status"] == "completed"
