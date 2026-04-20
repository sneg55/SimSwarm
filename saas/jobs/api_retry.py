"""Retry endpoints for the jobs API.

Split out of api.py to keep each router file under the project's 300-line
house limit. Lives behind the same /jobs prefix via include_router.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.dependencies import get_current_user
from saas.database import get_session
from saas.jobs.models import JobStatus, SimulationJob
from saas.jobs.schemas import JobCreate, JobResponse, TierEnum

router = APIRouter()


@router.post("/{job_id}/retry", response_model=JobResponse, status_code=201)
async def retry_job(
    job_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Retry a failed job with the same seed_text, goal, and tier."""
    from saas.jobs.api import create_job

    original = await session.get(SimulationJob, job_id)
    if not original:
        raise HTTPException(status_code=404, detail="Job not found")
    if original.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if original.status not in (JobStatus.FAILED, JobStatus.REFUNDED):
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    body = JobCreate(
        seed_text=original.seed_text,
        goal=original.goal,
        tier=TierEnum(original.tier),
        forecast_days=original.forecast_days if original.forecast_days is not None else 30,
    )
    new_job = await create_job(request, body, current_user, session)

    await session.execute(
        text("UPDATE simulation_jobs SET retry_of = :original_id WHERE id = :new_id"),
        {"original_id": original.id, "new_id": new_job.id},
    )
    await session.commit()
    return new_job


@router.post("/{job_id}/enrich-retry", status_code=202)
async def retry_enrichment(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Re-run seed enrichment for a job that failed enrichment."""
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    from saas.jobs.tasks import enrich_retry_task
    enrich_retry_task.delay(job_id=job.id, seed_text=job.seed_text, goal=job.goal)
    return {"status": "retrying"}
