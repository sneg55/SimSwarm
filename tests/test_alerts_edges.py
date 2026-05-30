"""Additional alert edge cases for coverage."""
from unittest.mock import MagicMock, patch

from saas.jobs.alerts import send_orphan_alert


@patch("saas.jobs.alerts.httpx")
def test_send_orphan_alert_with_job_id(mock_httpx):
    """job_id appears in message when provided."""
    mock_httpx.post.return_value = MagicMock(status_code=200)

    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": "https://hooks.slack.com/test"}):
        send_orphan_alert(
            pod_id="pod1", gpu_type="H100", uptime_seconds=7200,
            reason="orphan", job_id=123,
        )

    kwargs = mock_httpx.post.call_args.kwargs
    text = kwargs["json"]["text"]
    assert "Job ID: 123" in text
    # H100 has a known rate
    assert "H100" in text


@patch("saas.jobs.alerts.httpx")
def test_send_orphan_alert_unknown_gpu_rate(mock_httpx):
    """Unknown GPU type still produces a message (uses default rate)."""
    mock_httpx.post.return_value = MagicMock(status_code=200)
    with patch.dict("os.environ", {"ALERT_WEBHOOK_URL": "https://hooks.slack.com/x"}):
        send_orphan_alert(pod_id="p", gpu_type="Unknown GPU", uptime_seconds=3600, reason="r")
    assert mock_httpx.post.called
