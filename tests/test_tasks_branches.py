"""Additional Celery task branches: retry, enrichment, refund paths."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from saas.gpu.provider import GPUInstance


def _make_instance():
    return GPUInstance(
        instance_id="inst-x", provider="runpod", gpu_type="GPU",
        ip_address="1.2.3.4", ssh_port=22, status="running",
    )


def _base_kwargs(**overrides):
    k = dict(
        job_id=1, user_id="u", seed_text="seed", goal="goal", tier="small",
        model_id="Q", gpu_type="GPU", max_rounds=5, vllm_args="",
        llm_api_key="k", openai_api_key="", credits_charged=30,
    )
    k.update(overrides)
    return k


def test_task_enriches_seed_when_enabled():
    from saas.jobs.tasks import run_simulation_task
    from saas.jobs.enrichment import EnrichmentResult

    provider = MagicMock()

    async def prov(cfg, on_created=None):
        return _make_instance()

    async def term(pid):
        return None

    provider.provision = prov
    provider.terminate = term

    result = {
        "job_id": 1, "status": "completed",
        "report": "This is a long enough insight line for extraction.",
        "chat_log": "[]", "graph_data": "{}", "pod_id": "inst-x",
        "provision_seconds": 5, "pipeline_seconds": 10,
    }

    enrichment = EnrichmentResult(summary="Web facts", citations=[{"url": "u", "title": "t"}])

    with patch("saas.jobs.tasks._get_gpu_provider", return_value=provider), \
         patch("saas.jobs.tasks.JobRunner.run", new_callable=AsyncMock, return_value=result), \
         patch("saas.jobs.enrichment.enrich_seed", return_value=enrichment), \
         patch("saas.jobs.tasks._update_enrichment") as mock_enr, \
         patch("saas.jobs.tasks._save_job_results"), \
         patch("saas.jobs.tasks._update_job_metadata"), \
         patch("saas.jobs.tasks._update_sim_data_available"):
        out = run_simulation_task(**_base_kwargs(enrich_web=True))

    assert out["status"] == "completed"
    mock_enr.assert_called_once()


def test_task_enrichment_empty_sends_alert():
    from saas.jobs.tasks import run_simulation_task

    provider = MagicMock()

    async def prov(cfg, on_created=None):
        return _make_instance()

    async def term(pid):
        return None

    provider.provision = prov
    provider.terminate = term

    result = {
        "job_id": 1, "status": "completed",
        "report": "r", "chat_log": "[]", "graph_data": "{}",
        "pod_id": "inst-x",
    }

    with patch("saas.jobs.tasks._get_gpu_provider", return_value=provider), \
         patch("saas.jobs.tasks.JobRunner.run", new_callable=AsyncMock, return_value=result), \
         patch("saas.jobs.enrichment.enrich_seed", return_value=None), \
         patch("saas.jobs.alerts.send_enrichment_alert") as mock_alert, \
         patch("saas.jobs.tasks._save_job_results"), \
         patch("saas.jobs.tasks._update_job_metadata"):
        run_simulation_task(**_base_kwargs(enrich_web=True))

    mock_alert.assert_called_once()


def test_task_failure_marks_job_failed_and_refunds():
    from saas.jobs.tasks import run_simulation_task

    provider = MagicMock()

    async def prov(cfg, on_created=None):
        return _make_instance()

    async def term(pid):
        return None

    provider.provision = prov
    provider.terminate = term

    with patch("saas.jobs.tasks._get_gpu_provider", return_value=provider), \
         patch("saas.jobs.tasks.JobRunner.run", new_callable=AsyncMock, side_effect=RuntimeError("permanent failure")), \
         patch("saas.gpu.errors.classify_gpu_error", return_value="permanent"), \
         patch("saas.jobs.tasks._mark_job_failed") as mf, \
         patch("saas.jobs.tasks._refund_credits") as rc:
        with pytest.raises(RuntimeError):
            run_simulation_task(**_base_kwargs(enrich_web=False, credits_charged=30))

    mf.assert_called_once()
    rc.assert_called_once()


def test_task_transient_error_triggers_retry():
    """Transient error with retries remaining -> self.retry()."""
    from saas.jobs.tasks import run_simulation_task

    provider = MagicMock()

    async def prov(cfg, on_created=None):
        return _make_instance()

    async def term(pid):
        return None

    provider.provision = prov
    provider.terminate = term

    with patch("saas.jobs.tasks._get_gpu_provider", return_value=provider), \
         patch("saas.jobs.tasks.JobRunner.run", new_callable=AsyncMock, side_effect=RuntimeError("transient glitch")), \
         patch("saas.gpu.errors.classify_gpu_error", return_value="transient"), \
         patch("saas.jobs.tasks._update_job_retry"):
        with pytest.raises(Exception):
            run_simulation_task(**_base_kwargs(enrich_web=False, credits_charged=30))


def test_enrich_retry_task_succeeds():
    from saas.jobs.tasks import enrich_retry_task
    from saas.jobs.enrichment import EnrichmentResult

    r = EnrichmentResult(summary="fact", citations=[])
    with patch("saas.jobs.enrichment.enrich_seed", return_value=r), \
         patch("saas.jobs.tasks._update_enrichment") as mupd:
        result = enrich_retry_task(job_id=9, seed_text="s", goal="g")
    assert result["status"] == "enriched"
    mupd.assert_called_once()


def test_enrich_retry_task_fails():
    from saas.jobs.tasks import enrich_retry_task
    with patch("saas.jobs.enrichment.enrich_seed", return_value=None):
        result = enrich_retry_task(job_id=9, seed_text="s", goal="g")
    assert result["status"] == "failed"


def test_cleanup_orphaned_pods_task():
    from saas.jobs.tasks import cleanup_orphaned_pods

    with patch("saas.jobs.tasks._cleanup_orphaned_pods_impl", return_value={"terminated": 2}):
        assert cleanup_orphaned_pods() == {"terminated": 2}


def test_recover_stale_jobs_task():
    from saas.jobs.tasks import recover_stale_jobs

    with patch("saas.jobs.tasks._recover_stale_jobs_impl", return_value={"recovered": 1}):
        assert recover_stale_jobs() == {"recovered": 1}
