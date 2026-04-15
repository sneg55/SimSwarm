"""Celery task for external-LLM report generation.

Runs after run_simulation_task completes with sim_data_uploaded=True.
Any failure path (permanent or retries-exhausted) marks the job FAILED
and issues a 100% credit refund.
"""
from __future__ import annotations

import logging
import os

from saas.adapters.anthropic_client import (
    AnthropicClient,
    AnthropicPermanentError,
    AnthropicTransientError,
)
from saas.constants.tiers import TIER_REPORT_TIMEOUT_S  # noqa: F401 — used in future
from saas.jobs.persistence import (
    _mark_job_failed,
    _save_report_result,
    _extract_key_insight,
)
from saas.jobs.persistence_sync import _load_job_artifacts
from saas.jobs.refund import _refund_credits
from simswarm.adapter import adapt_structured
from saas.jobs.report import (
    ReportArtifactsMissingError,
    ReportExhaustedError,
    ReportRunner,
)
from saas.storage.minio_download import put_report_md
from saas.workers.celery_app import celery_app
from saas.workers.utils import _run_async

logger = logging.getLogger(__name__)

# Retry schedule: 30s, 120s, 300s, 900s, 1800s — ~55 minute total window.
_RETRY_BACKOFF_S = [30, 120, 300, 900, 1800]


def _build_runner(job_id: int, goal: str) -> ReportRunner:
    client = AnthropicClient(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model=os.getenv("SMART_MODEL", "claude-opus-4-6"),
    )
    return ReportRunner(job_id=job_id, goal=goal, client=client)


def _load_credits_charged(job_id: int) -> int:
    """Read credits_charged from the DB so refund uses the authoritative value."""
    from sqlalchemy import text
    from saas.jobs.persistence import _get_sync_engine

    engine = _get_sync_engine()
    if engine is None:
        return 0
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT credits_charged FROM simulation_jobs WHERE id = :id"),
                {"id": job_id},
            ).first()
            if not row:
                return 0
            return int(row[0] or 0)
    finally:
        engine.dispose()


def _load_goal(job_id: int) -> str:
    from sqlalchemy import text
    from saas.jobs.persistence import _get_sync_engine

    engine = _get_sync_engine()
    if engine is None:
        return ""
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT goal FROM simulation_jobs WHERE id = :id"),
                {"id": job_id},
            ).first()
            return row[0] if row and row[0] else ""
    finally:
        engine.dispose()


@celery_app.task(
    name="fishcloud.generate_report",
    bind=True,
    max_retries=len(_RETRY_BACKOFF_S),
)
def generate_report_task(self, job_id: int, user_id: str) -> dict:
    """Run the external-LLM report generation loop for a completed sim.

    On transient errors: retries with escalating backoff, up to 5 attempts.
    On permanent errors or exhausted retries: marks job FAILED, refunds 100%.
    """
    goal = _load_goal(job_id)
    runner = _build_runner(job_id, goal)

    try:
        result = _run_async(runner.run())
    except AnthropicTransientError as exc:
        attempt = self.request.retries
        if attempt < len(_RETRY_BACKOFF_S):
            countdown = _RETRY_BACKOFF_S[attempt]
            logger.warning(
                "report.transient_retry job_id=%d attempt=%d countdown=%ds err=%s",
                job_id, attempt, countdown, exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        _finalize_as_failed(job_id, user_id, f"report_transient_exhausted: {exc}")
        raise
    except (AnthropicPermanentError, ReportArtifactsMissingError, ReportExhaustedError) as exc:
        _finalize_as_failed(job_id, user_id, f"report_generation_failed: {exc}")
        raise

    structured = _build_structured(job_id=job_id, result=result)
    key_insight = _extract_key_insight(result.report_markdown)

    _save_report_result(
        job_id=job_id,
        report_markdown=result.report_markdown,
        structured=structured,
        key_insight=key_insight,
    )
    try:
        put_report_md(job_id, result.report_markdown)
    except Exception as exc:  # noqa: BLE001 — non-fatal; DB row is authoritative
        logger.warning("report.minio_upload_failed job_id=%d err=%s", job_id, exc)

    logger.info(
        "report.completed job_id=%d chars=%d findings=%d",
        job_id, len(result.report_markdown), len(result.findings),
    )
    return {"status": "completed", "report_chars": len(result.report_markdown)}


def _finalize_as_failed(job_id: int, user_id: str, reason: str) -> None:
    """Mark failed and refund 100%."""
    _mark_job_failed(job_id=job_id, error_message=reason)
    credits = _load_credits_charged(job_id)
    if credits > 0:
        _refund_credits(job_id=job_id, user_id=user_id, credits=credits)
    logger.warning("report.failed job_id=%d reason=%s refunded=%d", job_id, reason, credits)


def _build_structured(job_id: int, result) -> str:
    """Produce the full structured_results JSON string consumed by the Vue
    SimulationResults Story view. Loads the chat log + graph the sim task
    already wrote to the DB, then delegates to simswarm.adapter.adapt_structured
    so `brief`, correctly-shaped `findings`, `confidence`, `coalitions`,
    and `sentiment` are all present."""
    import json as _json

    chat_log_json, graph_json = _load_job_artifacts(job_id)
    try:
        chat_log = _json.loads(chat_log_json) if chat_log_json else []
    except _json.JSONDecodeError:
        chat_log = []
    try:
        graph_data = _json.loads(graph_json) if graph_json else {}
    except _json.JSONDecodeError:
        graph_data = {}

    structured_dict = adapt_structured(
        brief=result.executive_brief,
        findings=result.findings,
        chat_log=chat_log,
        graph_data=graph_data,
    )
    return _json.dumps(structured_dict)
