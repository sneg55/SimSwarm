"""Coverage for saas.jobs.tasks_resume.resume_simulation_task."""
from unittest.mock import AsyncMock, MagicMock, patch


def test_resume_skip_already_complete():
    from saas.jobs.tasks_resume import resume_simulation_task

    with patch("saas.jobs.tasks_resume._get_job_status", return_value="COMPLETED"):
        result = resume_simulation_task(
            job_id=1, user_id="u", pod_id="p", credits_charged=30,
        )
    assert result["skipped"] is True
    assert result["status"] == "already_completed"


def test_resume_skip_claim_rejected():
    from saas.jobs.tasks_resume import resume_simulation_task

    with patch("saas.jobs.tasks_resume._get_job_status", return_value="RUNNING"), \
         patch("saas.jobs.tasks_resume._claim_resume", return_value=False):
        result = resume_simulation_task(
            job_id=1, user_id="u", pod_id="p", credits_charged=30,
        )
    assert result["skipped"] is True
    assert result["status"] == "already_claimed"


def test_resume_success_saves_results():
    from saas.jobs.tasks_resume import resume_simulation_task

    mock_provider = MagicMock()
    result_data = {
        "job_id": 1, "status": "completed",
        "report": "A substantial report body line that meets length threshold.",
        "chat_log": "[]", "graph_data": "{}", "structured": "{}",
        "sim_data_uploaded": True,
    }

    with patch("saas.jobs.tasks_resume._get_job_status", return_value="RUNNING"), \
         patch("saas.jobs.tasks_resume._claim_resume", return_value=True), \
         patch("saas.jobs.tasks_resume._get_gpu_provider", return_value=mock_provider), \
         patch("saas.jobs.tasks_resume.JobRunner.resume", new_callable=AsyncMock, return_value=result_data), \
         patch("saas.jobs.tasks_resume._save_job_results") as save, \
         patch("saas.jobs.tasks_resume._update_sim_data_available") as usda, \
         patch("saas.jobs.tasks_resume._transition_to_reporting") as trans, \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async") as enqueue, \
         patch("saas.jobs.tasks_resume._release_resume") as rel:
        out = resume_simulation_task(
            job_id=1, user_id="u", pod_id="p", credits_charged=0,
        )

    assert out["status"] == "completed"
    save.assert_called_once()
    usda.assert_called_once()
    trans.assert_called_once_with(1)
    enqueue.assert_called_once_with((1, "u"))
    rel.assert_called_once()


def test_resume_failure_refunds_and_terminates():
    from saas.jobs.tasks_resume import resume_simulation_task

    mock_provider = MagicMock()

    async def fake_terminate(pod_id):
        return None

    mock_provider.terminate = fake_terminate

    with patch("saas.jobs.tasks_resume._get_job_status", return_value="RUNNING"), \
         patch("saas.jobs.tasks_resume._claim_resume", return_value=True), \
         patch("saas.jobs.tasks_resume._get_gpu_provider", return_value=mock_provider), \
         patch("saas.jobs.tasks_resume.JobRunner.resume", new_callable=AsyncMock, side_effect=RuntimeError("fail")), \
         patch("saas.jobs.tasks_resume._mark_job_failed") as mark, \
         patch("saas.jobs.tasks_resume._refund_credits") as refund, \
         patch("saas.jobs.tasks_resume._release_resume"):
        import pytest
        with pytest.raises(RuntimeError):
            resume_simulation_task(
                job_id=1, user_id="u", pod_id="p", credits_charged=30,
            )

    mark.assert_called_once()
    refund.assert_called_once()


# ---------------------------------------------------------------------------
# Race with main task — resume must not clobber a just-completed job
# ---------------------------------------------------------------------------


def _run_resume_failure_with_statuses(initial_status: str, second_status: str):
    """Drive resume_simulation_task through its except handler with a given
    pair of job-status readings: one at entry, one inside the except handler.
    Returns (mark_called, refund_called).
    """
    from saas.jobs.tasks_resume import resume_simulation_task

    mock_provider = MagicMock()

    async def fake_terminate(pod_id):
        return None

    mock_provider.terminate = fake_terminate

    # _get_job_status is called twice: once at task entry (to skip already-
    # complete jobs), once inside the except handler (the new guard).
    status_values = iter([initial_status, second_status])

    def status_side_effect(_job_id):
        return next(status_values)

    with patch("saas.jobs.tasks_resume._get_job_status", side_effect=status_side_effect), \
         patch("saas.jobs.tasks_resume._claim_resume", return_value=True), \
         patch("saas.jobs.tasks_resume._get_gpu_provider", return_value=mock_provider), \
         patch("saas.jobs.tasks_resume.JobRunner.resume", new_callable=AsyncMock,
               side_effect=RuntimeError("Pod unreachable: 5 consecutive poll failures")), \
         patch("saas.jobs.tasks_resume._mark_job_failed") as mark, \
         patch("saas.jobs.tasks_resume._refund_credits") as refund, \
         patch("saas.jobs.tasks_resume._release_resume"):
        import pytest
        with pytest.raises(RuntimeError):
            resume_simulation_task(
                job_id=1, user_id="u", pod_id="p", credits_charged=30,
            )
    return mark, refund


def test_resume_failure_skips_mark_failed_when_job_moved_to_reporting():
    """The phantom-resume race: main task completes and moves the job to
    REPORTING just as resume's poll loop dies. Resume must NOT overwrite
    that state with FAILED, and must NOT refund credits."""
    mark, refund = _run_resume_failure_with_statuses("RUNNING", "REPORTING")
    mark.assert_not_called()
    refund.assert_not_called()


def test_resume_failure_skips_mark_failed_when_job_already_completed():
    """If the main task has already pushed the job all the way to COMPLETED,
    resume's failure path is meaningless — no mark, no refund."""
    mark, refund = _run_resume_failure_with_statuses("RUNNING", "COMPLETED")
    mark.assert_not_called()
    refund.assert_not_called()


def test_resume_failure_still_marks_failed_when_job_still_in_scope():
    """Regression guard for the happy failure path: when the job is still in
    PROVISIONING/RUNNING, resume owns the failure state and should mark it."""
    mark, refund = _run_resume_failure_with_statuses("RUNNING", "RUNNING")
    mark.assert_called_once()
    refund.assert_called_once()
