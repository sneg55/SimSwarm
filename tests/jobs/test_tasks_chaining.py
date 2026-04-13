"""Tests for run_simulation_task → generate_report_task chaining."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from saas.jobs.tasks import run_simulation_task


def _runner_returning(result_dict):
    runner = MagicMock()

    async def _fake_run(config):
        return result_dict
    runner.run.side_effect = _fake_run
    return runner


def _baseline_kwargs():
    return dict(
        job_id=42,
        user_id="u1",
        seed_text="seed",
        goal="g",
        tier="small",
        model_id="m",
        gpu_type="L40S",
        max_rounds=15,
        vllm_args="",
        llm_api_key="k",
        credits_charged=30,
        enrich_web=False,
        target_agents=3,
    )


def test_successful_sim_enqueues_report_task():
    with patch("saas.jobs.tasks.JobRunner") as JR, \
         patch("saas.jobs.tasks._save_job_results") as save, \
         patch("saas.jobs.tasks._update_sim_data_available") as upd_sd, \
         patch("saas.jobs.tasks._transition_to_reporting") as trans, \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async") as enqueue, \
         patch("saas.jobs.tasks._get_gpu_provider"):
        JR.return_value = _runner_returning({
            "report": "",
            "chat_log": "[]",
            "graph_data": "{}",
            "structured": "{}",
            "sim_data_uploaded": True,
            "pod_id": "pod-x",
            "provision_seconds": 30,
            "pipeline_seconds": 60,
        })
        run_simulation_task.run(**_baseline_kwargs())

    save.assert_called_once()
    upd_sd.assert_called_once_with(42, True)
    trans.assert_called_once_with(42)
    enqueue.assert_called_once()
    (args,), _ = enqueue.call_args
    assert args == (42, "u1")


def test_failed_upload_marks_failed_and_refunds_no_report_task():
    with patch("saas.jobs.tasks.JobRunner") as JR, \
         patch("saas.jobs.tasks._save_job_results"), \
         patch("saas.jobs.tasks._mark_job_failed") as fail, \
         patch("saas.jobs.tasks._refund_credits") as refund, \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async") as enqueue, \
         patch("saas.jobs.tasks._get_gpu_provider"):
        JR.return_value = _runner_returning({
            "report": "",
            "chat_log": "[]",
            "graph_data": "{}",
            "structured": "{}",
            "sim_data_uploaded": False,
            "pod_id": "pod-y",
        })
        run_simulation_task.run(**_baseline_kwargs())

    fail.assert_called_once()
    refund.assert_called_once_with(job_id=42, user_id="u1", credits=30)
    enqueue.assert_not_called()
