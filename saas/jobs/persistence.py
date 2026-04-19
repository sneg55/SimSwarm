"""DB write helpers for SimulationJob persistence.

This module is a re-export shim. Implementation lives in:
  - persistence_engine.py  — engine/session factory helpers
  - persistence_sync.py    — sync (psycopg2) helpers for Celery tasks
  - persistence_async.py   — async helpers for async contexts
"""
from __future__ import annotations

import logging

# Engine helpers (imported first — used by functions defined below)
from saas.jobs.persistence_engine import (
    _get_sync_engine,
    _get_worker_session_factory,
)

# Sync helpers (psycopg2 / Celery-safe) — split across two files by concern
from saas.jobs.persistence_sync import (
    _mark_job_failed_sync,
    _save_job_results,
    _update_job_retry_sync,
    _get_job_status,
    _get_job_config_for_resume,
    _transition_to_reporting,
    _save_report_result,
)
from saas.jobs.persistence_sync_progress import (
    _update_pipeline_stage_sync,
    _update_heartbeat_sync,
    _update_live_status_sync,
    _update_pod_id,
    _update_sim_data_available,
    _update_enrichment_sync,
    _update_markets_config_sync,
)
from saas.jobs.persistence_sync_idempotency import (
    _load_job_snapshot,
    _transition_to_running,
)

# Async helpers
from saas.jobs.persistence_async import (
    _update_pipeline_stage,
    _async_update_pipeline_stage,
    _async_update_pod_id,
    _update_job_metadata,
    _update_heartbeat,
    _async_update_heartbeat,
)

# Aliases: tasks.py imports these names — route to the sync versions
_update_enrichment = _update_enrichment_sync
_update_markets_config = _update_markets_config_sync
_mark_job_failed = _mark_job_failed_sync
_update_job_retry = _update_job_retry_sync

logger = logging.getLogger(__name__)


def _derive_key_insight(verdict: str, report_markdown: str) -> str | None:
    """Prefer the LLM-authored verdict; fall back to first non-heading line.

    The fallback exists only for defensive reasons — a well-formed report
    will always have a verdict (Task 14 prompt demands it).
    """
    if verdict and verdict.strip():
        return verdict.strip()[:200]
    if not report_markdown:
        return None
    lines = [line.strip() for line in report_markdown.split("\n") if line.strip()]
    insight_line = next(
        (line for line in lines if not line.startswith("#") and len(line) > 30),
        None,
    )
    return insight_line[:200] if insight_line else None


# Keep the old name as a back-compat shim for one release cycle.
# Delete inline callers in this PR.
_extract_key_insight = _derive_key_insight


__all__ = [
    "_derive_key_insight",
    "_extract_key_insight",
    "_get_sync_engine",
    "_get_worker_session_factory",
    "_mark_job_failed_sync",
    "_save_job_results",
    "_update_job_retry_sync",
    "_update_pipeline_stage_sync",
    "_update_heartbeat_sync",
    "_update_live_status_sync",
    "_update_pod_id",
    "_update_sim_data_available",
    "_update_enrichment_sync",
    "_update_markets_config_sync",
    "_update_markets_config",
    "_get_job_status",
    "_get_job_config_for_resume",
    "_transition_to_reporting",
    "_save_report_result",
    "_mark_job_failed",
    "_update_pipeline_stage",
    "_async_update_pipeline_stage",
    "_async_update_pod_id",
    "_update_job_metadata",
    "_update_heartbeat",
    "_async_update_heartbeat",
    "_update_enrichment",
    "_update_job_retry",
    "_load_job_snapshot",
    "_transition_to_running",
]
