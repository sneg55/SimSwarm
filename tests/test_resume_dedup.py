"""Tests for resume_simulation_task deduplication."""
from unittest.mock import patch, MagicMock

import pytest


def _resume_fn():
    """Return the raw (unbound) resume_simulation_task function.

    Celery wraps ``bind=True`` tasks as bound methods on a PromiseProxy.
    Calling the proxy directly injects the task instance as ``self``, which
    conflicts with an explicit ``mock_self`` positional argument.  Using
    ``__wrapped__.__func__`` gives us the plain Python function so we can
    pass our own mock as ``self`` and patch module-level helpers cleanly.
    """
    from saas.jobs.tasks import resume_simulation_task
    return resume_simulation_task.__wrapped__.__func__


class TestResumeDedup:
    """Verify that duplicate resume tasks are rejected."""

    def test_resume_skips_when_claim_fails(self):
        """When _claim_resume returns False, task exits without running."""
        fn = _resume_fn()

        mock_self = MagicMock()
        mock_self.request = MagicMock()
        mock_self.request.id = "task-dup"

        with patch("saas.jobs.tasks._get_job_status", return_value="RUNNING"), \
             patch("saas.jobs.tasks._claim_resume", return_value=False) as mock_claim:
            result = fn(
                mock_self,
                job_id=42,
                user_id="user-1",
                pod_id="pod-abc",
                credits_charged=100,
            )

        assert result["skipped"] is True
        mock_claim.assert_called_once_with(42, "task-dup")

    def test_resume_releases_claim_on_success(self):
        """On successful resume, claim is released."""
        fn = _resume_fn()

        mock_self = MagicMock()
        mock_self.request = MagicMock()
        mock_self.request.id = "task-ok"

        mock_result = {
            "report": "# Report",
            "chat_log": "[]",
            "graph_data": "{}",
            "structured": "{}",
        }

        with patch("saas.jobs.tasks._get_job_status", return_value="RUNNING"), \
             patch("saas.jobs.tasks._claim_resume", return_value=True), \
             patch("saas.jobs.tasks._release_resume") as mock_release, \
             patch("saas.jobs.tasks._get_gpu_provider"), \
             patch("saas.jobs.tasks._run_async", return_value=mock_result), \
             patch("saas.jobs.tasks._save_job_results"):
            result = fn(
                mock_self,
                job_id=42,
                user_id="user-1",
                pod_id="pod-abc",
                credits_charged=100,
            )

        mock_release.assert_called_once_with(42)
        assert result["report"] == "# Report"

    def test_resume_releases_claim_on_failure(self):
        """On failed resume, claim is still released."""
        fn = _resume_fn()

        mock_self = MagicMock()
        mock_self.request = MagicMock()
        mock_self.request.id = "task-fail"

        with patch("saas.jobs.tasks._get_job_status", return_value="RUNNING"), \
             patch("saas.jobs.tasks._claim_resume", return_value=True), \
             patch("saas.jobs.tasks._release_resume") as mock_release, \
             patch("saas.jobs.tasks._get_gpu_provider"), \
             patch("saas.jobs.tasks._run_async", side_effect=RuntimeError("pod gone")), \
             patch("saas.jobs.tasks._mark_job_failed"), \
             patch("saas.jobs.tasks._refund_credits"):
            with pytest.raises(RuntimeError, match="pod gone"):
                fn(
                    mock_self,
                    job_id=42,
                    user_id="user-1",
                    pod_id="pod-abc",
                    credits_charged=100,
                )

        mock_release.assert_called_once_with(42)
