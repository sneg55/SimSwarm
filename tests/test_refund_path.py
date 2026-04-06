"""Test that refund path is correct."""
import inspect
from unittest.mock import patch, MagicMock


def test_refund_credits_uses_credit_entries_table():
    from saas.jobs.tasks import _refund_credits
    source = inspect.getsource(_refund_credits)
    assert "credit_entries" in source
    assert "credit_ledger" not in source


async def test_job_dispatch_passes_credits_charged(client, auth_headers, funded_user, seeded_routing):
    mock_task = MagicMock()
    mock_task.id = "celery-mock"
    with patch("saas.jobs.api.run_simulation_task.delay", return_value=mock_task) as mock_delay:
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={"seed_text": "Test seed text for dispatch.", "goal": "Test goal", "tier": "small"},
        )
    assert resp.status_code == 201
    kwargs = mock_delay.call_args.kwargs
    assert kwargs.get("credits_charged") == 30
