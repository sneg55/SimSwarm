import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.models.job import SimulationJob, JobStatus
from saas.models.model_routing import ModelRouting
from saas.schemas.jobs import JobCreate, JobResponse, JobListResponse
from saas.tiers import TIER_CREDITS
from saas.billing.ledger import CreditLedger, InsufficientCreditsError
from saas.auth.dependencies import get_current_user
import os

from saas.workers.tasks import run_simulation_task

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    request: Request,
    body: JobCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    max_seed_chars = request.app.state.settings.MAX_SEED_CHARS
    if len(body.seed_text) > max_seed_chars:
        raise HTTPException(
            status_code=400,
            detail=f"Seed text exceeds maximum of {max_seed_chars} characters",
        )

    user_id = current_user["user_id"]
    credits = TIER_CREDITS[body.tier]

    # 1. Validate routing exists BEFORE touching credits
    route = await session.execute(
        select(ModelRouting).where(ModelRouting.sim_tier == body.tier.value)
    )
    routing = route.scalar_one_or_none()
    if not routing:
        raise HTTPException(
            status_code=500,
            detail=f"No model routing configured for tier: {body.tier.value}",
        )

    # 2. Debit credits (raises 402 if insufficient — no commit yet)
    ledger = CreditLedger(session)
    try:
        await ledger.debit(
            user_id=user_id,
            amount=credits,
            description=f"Job creation — tier {body.tier.value}",
        )
    except InsufficientCreditsError:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Required: {credits}",
        )

    # 3. Create job row (not committed yet)
    job = SimulationJob(
        user_id=user_id,
        seed_text=body.seed_text,
        goal=body.goal,
        tier=body.tier.value,
        credits_charged=credits,
        status=JobStatus.PENDING,
        enrich_web=body.enrich_web,
        forecast_days=body.forecast_days,
    )
    session.add(job)
    await session.flush()  # get job.id without committing

    # 4. Dispatch to Celery — if this fails, the whole transaction rolls back
    try:
        task_result = run_simulation_task.delay(
            job_id=job.id,
            user_id=user_id,
            seed_text=body.seed_text,
            goal=body.goal,
            tier=body.tier.value,
            model_id=routing.model_id,
            gpu_type=routing.gpu_type,
            max_rounds=routing.max_rounds,
            vllm_args=routing.vllm_args or "",
            llm_api_key=os.getenv("LLM_API_KEY", "not-needed"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            credits_charged=credits,
            enrich_web=body.enrich_web,
            forecast_days=body.forecast_days,
        )
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to queue simulation job")

    # 5. Store task ID and commit everything atomically
    job.celery_task_id = task_result.id
    await session.commit()
    await session.refresh(job)

    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this job")
    await session.delete(job)
    await session.commit()


@router.post("/{job_id}/retry", response_model=JobResponse, status_code=201)
async def retry_job(
    job_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Retry a failed job with the same seed_text, goal, and tier."""
    original = await session.get(SimulationJob, job_id)
    if not original:
        raise HTTPException(status_code=404, detail="Job not found")
    if original.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if original.status not in (JobStatus.FAILED, JobStatus.REFUNDED):
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")

    from saas.schemas.jobs import TierEnum
    body = JobCreate(seed_text=original.seed_text, goal=original.goal, tier=TierEnum(original.tier))
    new_job = await create_job(request, body, current_user, session)

    # Link new job to original so dashboard hides the superseded failure
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

    from saas.workers.tasks import enrich_retry_task
    enrich_retry_task.delay(job_id=job.id, seed_text=job.seed_text, goal=job.goal)
    return {"status": "retrying"}


@router.get("/{job_id}/graph")
async def get_job_graph(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    import json

    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
    if not job.result_graph:
        raise HTTPException(status_code=404, detail="Graph data not available for this job")
    try:
        json.loads(job.result_graph)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=500, detail="Invalid graph data stored for this job")
    return Response(content=job.result_graph, media_type="application/json")


@router.get("", response_model=JobListResponse)
async def list_jobs(
    page: int = 1,
    per_page: int = 10,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = current_user["user_id"]

    # IDs of jobs that have been superseded by a retry
    superseded_q = select(SimulationJob.retry_of).where(
        SimulationJob.user_id == user_id,
        SimulationJob.retry_of.is_not(None),
    )
    superseded_ids = {row[0] for row in (await session.execute(superseded_q)).all()}

    base = select(SimulationJob).where(
        SimulationJob.user_id == user_id,
        SimulationJob.id.notin_(superseded_ids) if superseded_ids else True,
    )

    total_result = await session.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar_one()

    result = await session.execute(
        base.order_by(SimulationJob.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    jobs = result.scalars().all()
    return JobListResponse(jobs=jobs, total=total, page=page, per_page=per_page)


@router.post("/{job_id}/share")
async def create_share_link(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404)
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403)
    if job.status.value != "COMPLETED":
        raise HTTPException(status_code=400, detail="Can only share completed jobs")

    if not job.share_token:
        job.share_token = secrets.token_urlsafe(32)
        await session.commit()

    return {"share_token": job.share_token, "share_url": f"/s/{job.share_token}"}


@router.delete("/{job_id}/share")
async def revoke_share_link(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404)
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403)
    job.share_token = None
    await session.commit()
    return {"status": "revoked"}
