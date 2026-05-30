"""Celery task for external-LLM report generation.

Runs after run_simulation_task completes with sim_data_uploaded=True.
Any failure path (permanent or retries-exhausted) marks the job FAILED.
"""
from __future__ import annotations

import json
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
    _derive_key_insight,
)
from saas.jobs.persistence_sync import _load_job_artifacts
from saas.jobs.report import (
    ReportArtifactsMissingError,
    ReportExhaustedError,
    ReportRunner,
)
from saas.storage.minio_download import put_report_md
from saas.workers.celery_app import celery_app
from saas.workers.utils import _run_async
from simswarm.adapter import adapt_structured

logger = logging.getLogger(__name__)

# Retry schedule: 30s, 120s, 300s, 900s, 1800s — ~55 minute total window.
_RETRY_BACKOFF_S = [30, 120, 300, 900, 1800]


def _build_runner(job_id: int, goal: str, forecast_days: int) -> ReportRunner:
    client = AnthropicClient(
        api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        model=os.getenv("SMART_MODEL", "claude-opus-4-6"),
    )
    return ReportRunner(job_id=job_id, goal=goal, forecast_days=forecast_days, client=client)


def _load_goal_and_forecast(job_id: int) -> tuple[str, int]:
    from sqlalchemy import text
    from saas.jobs.persistence import _get_sync_engine

    engine = _get_sync_engine()
    if engine is None:
        return "", 30
    try:
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT goal, forecast_days FROM simulation_jobs WHERE id = :id"),
                {"id": job_id},
            ).first()
            if not row:
                return "", 30
            goal = row[0] or ""
            forecast_days = int(row[1] or 30)
            return goal, forecast_days
    finally:
        engine.dispose()


@celery_app.task(
    name="fishcloud.generate_report",
    bind=True,
    max_retries=len(_RETRY_BACKOFF_S),
)
def generate_report_task(self, job_id: int, user_id: str) -> dict:
    """Generate the external report for a completed sim.

    Idempotency guard: if the job is already in a terminal state, skip —
    this prevents double-generation when upload_and_finalize is retried
    after a transient failure mid-way through its work.

    On transient errors: retries with escalating backoff, up to 5 attempts.
    On permanent errors or exhausted retries: marks the job FAILED.
    """
    from saas.jobs.persistence import _get_job_status

    current_status = _get_job_status(job_id)
    if current_status in ("COMPLETED", "FAILED", "REFUNDED"):
        logger.info(
            "report.skipping_terminal job_id=%d status=%s",
            job_id, current_status,
        )
        return {"job_id": job_id, "status": "skipped_terminal"}

    return _run_report_generation(self, job_id, user_id)


def _run_report_generation(self, job_id: int, user_id: str) -> dict:
    """(Verbatim relocation of the previous ``generate_report_task`` body.)"""
    goal, forecast_days = _load_goal_and_forecast(job_id)
    runner = _build_runner(job_id, goal, forecast_days)

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

    try:
        structured = _build_structured(job_id=job_id, result=result)
        key_insight = _derive_key_insight(
            verdict=result.verdict,
            report_markdown=result.report_markdown,
        )
        _save_report_result(
            job_id=job_id,
            report_markdown=result.report_markdown,
            structured=structured,
            key_insight=key_insight,
        )
    except Exception as exc:
        _finalize_as_failed(job_id, user_id, f"report_persist_failed: {exc}")
        raise

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
    """Mark the job FAILED. (user_id kept in the signature for call-site
    compatibility; no longer used now that refunds are gone.)"""
    _mark_job_failed(job_id=job_id, error_message=reason)
    logger.warning("report.failed job_id=%d reason=%s", job_id, reason)


def _build_structured(job_id: int, result) -> str:
    """Produce the full structured_results JSON string consumed by the Vue
    SimulationResults Story view. Loads the chat log + graph the sim task
    already wrote to the DB, then delegates to simswarm.adapter.adapt_structured,
    which merges the LLM-authored `brief` + `verdict` + slotted `findings`
    with the deterministic Path 3 signals (`stakeholder_positions`,
    `named_coalitions`, `phase_boundaries`, `quotable_posts`,
    `disagreement_axis`, `sim_scale`) from simswarm.story_signals.

    Returns the full 9-key payload on the happy path. If the row's artifacts
    are absent (rare — a job id without persisted sim data), adapt_structured
    degrades gracefully on empty inputs. JSON decode errors propagate so the
    Celery task's failure path can mark the job failed."""
    chat_log_json, graph_json = _load_job_artifacts(job_id)
    chat_log = json.loads(chat_log_json) if chat_log_json else []
    graph_data = json.loads(graph_json) if graph_json else {}

    _, forecast_days = _load_goal_and_forecast(job_id)

    structured_dict = adapt_structured(
        brief=result.executive_brief,
        findings=result.findings,
        chat_log=chat_log,
        graph_data=graph_data,
        forecast_days=forecast_days,
        verdict=result.verdict,
    )
    return json.dumps(structured_dict)
