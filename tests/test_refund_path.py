"""Test that refund path is correct."""
import inspect
from unittest.mock import patch, MagicMock, AsyncMock


def test_refund_credits_uses_credit_entries_table():
    from saas.jobs.refund import _refund_credits
    source = inspect.getsource(_refund_credits)
    assert "credit_entries" in source
    assert "credit_ledger" not in source


async def test_job_dispatch_passes_credits_charged(client, auth_headers, funded_user, seeded_routing):
    fake_handle = MagicMock()
    fake_handle.id = "sim-mock-id"
    fake_handle.result_run_id = "run-mock"
    fake_client = AsyncMock()
    mock_start = AsyncMock(return_value=fake_handle)
    fake_client.start_workflow = mock_start
    with patch("saas.jobs.api.get_temporal_client", new=AsyncMock(return_value=fake_client)):
        resp = await client.post(
            "/api/jobs",
            headers=auth_headers,
            json={
                "seed_text": "Test seed text for dispatch.",
                "goal": "Test goal",
                "tier": "small",
                "forecast_days": 30,
            },
        )
    assert resp.status_code == 201
    # Verify SimParams passed to start_workflow carries credits_charged=30
    call_args = mock_start.call_args
    sim_params = call_args.args[1]  # second positional arg is SimParams
    assert sim_params.credits_charged == 30
