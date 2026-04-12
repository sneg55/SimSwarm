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
         patch("saas.jobs.tasks_resume._release_resume") as rel:
        out = resume_simulation_task(
            job_id=1, user_id="u", pod_id="p", credits_charged=0,
        )

    assert out["status"] == "completed"
    save.assert_called_once()
    usda.assert_called_once()
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
