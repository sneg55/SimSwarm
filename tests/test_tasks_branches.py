"""Coverage for Celery task branches: enrichment and cleanup."""
from unittest.mock import patch

import pytest


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
