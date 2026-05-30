from unittest.mock import patch



def test_generate_report_task_skips_terminal_job():
    from saas.jobs.tasks_report import generate_report_task

    with patch("saas.jobs.persistence._get_job_status", return_value="COMPLETED") as mock_status:
        result = generate_report_task(job_id=99, user_id="u1")

    mock_status.assert_called_once_with(99)
    assert result == {"job_id": 99, "status": "skipped_terminal"}


def test_generate_report_task_proceeds_for_reporting_job():
    from saas.jobs.tasks_report import generate_report_task

    with patch("saas.jobs.persistence._get_job_status", return_value="REPORTING"), \
         patch("saas.jobs.tasks_report._run_report_generation") as mock_run:
        mock_run.return_value = {"job_id": 99, "status": "completed"}
        result = generate_report_task(job_id=99, user_id="u1")

    mock_run.assert_called_once()
    assert result["status"] == "completed"
