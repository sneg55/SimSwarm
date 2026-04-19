"""Idempotency preamble in run_simulation_task — redelivery handling."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import saas.jobs.tasks as tasks


def _task_kwargs(**overrides):
    defaults = dict(
        job_id=1,
        user_id="user-1",
        seed_text="s",
        goal="g",
        tier="small",
        model_id="Qwen/Qwen3-14B",
        gpu_type="L40S",
        max_rounds=15,
        vllm_args="",
        llm_api_key="sk-test",
        openai_api_key="",
        credits_charged=30,
        enrich_web=False,
    )
    defaults.update(overrides)
    return defaults


def test_preamble_skips_when_job_is_terminal():
    """Redelivery of a COMPLETED job must not re-run anything."""
    with patch("saas.jobs.tasks._load_job_snapshot",
               return_value=("COMPLETED", "pod-x", 0)), \
         patch("saas.jobs.market_derivation.derive_markets") as derive, \
         patch("saas.jobs.tasks._get_gpu_provider") as prov:
        result = tasks.run_simulation_task(**_task_kwargs())
    assert result == {"job_id": 1, "status": "skipped_terminal"}
    derive.assert_not_called()
    prov.assert_not_called()


def test_preamble_hands_off_to_resume_on_redelivery():
    """Redelivery of an active job hands off to resume_simulation_task."""
    with patch("saas.jobs.tasks._load_job_snapshot",
               return_value=("PROVISIONING", "pod-abc", 0)), \
         patch("saas.jobs.tasks_resume.resume_simulation_task.delay") as resume_delay, \
         patch("saas.jobs.market_derivation.derive_markets") as derive, \
         patch("saas.jobs.tasks._get_gpu_provider") as prov:
        result = tasks.run_simulation_task(**_task_kwargs(credits_charged=30))
    assert result["status"] == "handed_off"
    assert result["pod_id"] == "pod-abc"
    resume_delay.assert_called_once_with(
        job_id=1, user_id="user-1", pod_id="pod-abc", credits_charged=30,
    )
    derive.assert_not_called()
    prov.assert_not_called()


def test_preamble_does_not_hand_off_without_pod_id():
    """A PROVISIONING row with no pod_id is not a redelivery — fall through."""
    with patch("saas.jobs.tasks._load_job_snapshot",
               return_value=("PROVISIONING", None, 0)), \
         patch("saas.jobs.tasks_resume.resume_simulation_task.delay") as resume_delay, \
         patch("saas.jobs.market_derivation.derive_markets",
               return_value={"source": "fallback_goal",
                             "markets": [{"id": "m1"}]}), \
         patch("saas.jobs.tasks._update_markets_config"), \
         patch("saas.jobs.tasks._get_gpu_provider", return_value=MagicMock()), \
         patch("saas.jobs.tasks.JobRunner"), \
         patch("saas.jobs.tasks._run_async", return_value={
             "pod_id": "p", "provision_seconds": 1, "pipeline_seconds": 1,
             "report": "", "chat_log": "", "graph_data": "{}", "structured": "{}",
             "sim_data_uploaded": True,
         }), \
         patch("saas.jobs.tasks._save_job_results"), \
         patch("saas.jobs.tasks._update_sim_data_available"), \
         patch("saas.jobs.tasks._transition_to_reporting"), \
         patch("saas.jobs.tasks._update_job_metadata"), \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async"):
        tasks.run_simulation_task(**_task_kwargs())
    resume_delay.assert_not_called()


def test_preamble_falls_through_when_snapshot_unavailable():
    """DB read failure → None snapshot → proceed as fresh run."""
    with patch("saas.jobs.tasks._load_job_snapshot", return_value=None), \
         patch("saas.jobs.tasks_resume.resume_simulation_task.delay") as resume_delay, \
         patch("saas.jobs.market_derivation.derive_markets",
               return_value={"source": "fallback_goal",
                             "markets": [{"id": "m1"}]}), \
         patch("saas.jobs.tasks._update_markets_config"), \
         patch("saas.jobs.tasks._get_gpu_provider", return_value=MagicMock()), \
         patch("saas.jobs.tasks.JobRunner"), \
         patch("saas.jobs.tasks._run_async", return_value={
             "pod_id": "p", "provision_seconds": 1, "pipeline_seconds": 1,
             "report": "", "chat_log": "", "graph_data": "{}", "structured": "{}",
             "sim_data_uploaded": True,
         }), \
         patch("saas.jobs.tasks._save_job_results"), \
         patch("saas.jobs.tasks._update_sim_data_available"), \
         patch("saas.jobs.tasks._transition_to_reporting"), \
         patch("saas.jobs.tasks._update_job_metadata"), \
         patch("saas.jobs.tasks_report.generate_report_task.apply_async"):
        tasks.run_simulation_task(**_task_kwargs())
    resume_delay.assert_not_called()
