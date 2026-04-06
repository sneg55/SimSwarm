"""Tests for webhook alerting."""
from unittest.mock import patch, MagicMock

from saas.jobs.alerts import send_orphan_alert


@patch("saas.jobs.alerts.httpx")
def test_send_orphan_alert_posts_to_webhook(mock_httpx):
    """Alert should POST JSON to the configured webhook URL."""
    mock_httpx.post.return_value = MagicMock(status_code=200)

    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        send_orphan_alert(
            pod_id="pod-abc",
            gpu_type="L40S",
            uptime_seconds=3600,
            reason="orphan",
        )

    mock_httpx.post.assert_called_once()
    args, kwargs = mock_httpx.post.call_args
    assert args[0] == "https://hooks.slack.com/test"
    assert "pod-abc" in kwargs["json"]["text"]
    assert "L40S" in kwargs["json"]["text"]


@patch("saas.jobs.alerts.httpx")
def test_send_orphan_alert_noop_without_webhook_url(mock_httpx):
    """Alert should do nothing when ALERT_WEBHOOK_URL is not set."""
    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": ""}, clear=False):
        send_orphan_alert(pod_id="pod-abc", gpu_type="L40S", uptime_seconds=3600, reason="orphan")

    mock_httpx.post.assert_not_called()


@patch("saas.jobs.alerts.httpx")
def test_send_orphan_alert_swallows_errors(mock_httpx):
    """Alert failure must never raise -- fire and forget."""
    mock_httpx.post.side_effect = Exception("network error")

    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        send_orphan_alert(pod_id="pod-abc", gpu_type="L40S", uptime_seconds=3600, reason="orphan")
