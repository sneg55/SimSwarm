"""Draft campaign API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.jobs.models import SimulationJob, JobStatus, ModelRouting
from saas.jobs.schemas import DraftCreate, DraftUpdate, JobResponse
from saas.constants.tiers import TIER_CREDITS
from saas.billing.ledger import CreditLedger, InsufficientCreditsError
from saas.auth.dependencies import get_current_user
from saas.storage.minio_client import SimDataStorage
from saas.jobs.tasks import run_simulation_task

import os

router = APIRouter(prefix="/draft", tags=["drafts"])


def _get_sim_data_storage(request: Request) -> SimDataStorage:
    settings = request.app.state.settings
    return SimDataStorage(
        endpoint=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        bucket=settings.MINIO_BUCKET,
        secure=settings.MINIO_SECURE,
        proxy_base=settings.MINIO_PROXY_BASE,
    )


async def _get_user_draft(
    job_id: int, user_id: str, session: AsyncSession
) -> SimulationJob:
    """Fetch a draft owned by the user, or raise 404/409."""
    job = await session.get(SimulationJob, job_id)
    if not job or job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Draft not found")
    if job.status != JobStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Job is not a draft")
    return job


@router.post("", response_model=JobResponse, status_code=201)
async def create_draft(
    body: DraftCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new draft with partial data. No credit check."""
    job = SimulationJob(
        user_id=current_user["user_id"],
        seed_text=body.seed_text,
        goal=body.goal,
        tier=body.tier.value if body.tier else None,
        credits_charged=0,
        status=JobStatus.DRAFT,
        enrich_web=body.enrich_web,
        forecast_days=body.forecast_days,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


@router.patch("/{job_id}", response_model=JobResponse)
async def update_draft(
    job_id: int,
    body: DraftUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update an existing draft. Only works when status == DRAFT."""
    job = await _get_user_draft(job_id, current_user["user_id"], session)

    max_seed_chars = request.app.state.settings.MAX_SEED_CHARS
    if body.seed_text is not None:
        if len(body.seed_text) > max_seed_chars:
            raise HTTPException(
                status_code=400,
                detail=f"Seed text exceeds maximum of {max_seed_chars} characters",
            )
        job.seed_text = body.seed_text
    if body.goal is not None:
        job.goal = body.goal
    if body.tier is not None:
        job.tier = body.tier.value
    if body.enrich_web is not None:
        job.enrich_web = body.enrich_web
    if body.forecast_days is not None:
        job.forecast_days = body.forecast_days

    await session.commit()
    await session.refresh(job)
    return job


@router.post("/{job_id}/launch", response_model=JobResponse)
async def launch_draft(
    job_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Launch a complete draft: validate, debit credits, dispatch to Celery."""
    user_id = current_user["user_id"]
    job = await _get_user_draft(job_id, user_id, session)

    # 1. Validate completeness
    missing = []
    if not job.seed_text or not job.seed_text.strip():
        missing.append("seed_text")
    if not job.goal or not job.goal.strip():
        missing.append("goal")
    if not job.tier:
        missing.append("tier")
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Draft is incomplete, missing: {', '.join(missing)}",
        )

    if job.forecast_days is None:
        raise HTTPException(
            status_code=422,
            detail={
                "field": "forecast_days",
                "message": "forecast_days is required to launch a simulation",
            },
        )

    # 2. Validate routing
    route = await session.execute(
        select(ModelRouting).where(ModelRouting.sim_tier == job.tier)
    )
    routing = route.scalar_one_or_none()
    if not routing:
        raise HTTPException(
            status_code=500,
            detail=f"No model routing configured for tier: {job.tier}",
        )

    # 3. Debit credits
    credits = TIER_CREDITS[job.tier]
    ledger = CreditLedger(session)
    try:
        await ledger.debit(
            user_id=user_id,
            amount=credits,
            description=f"Job creation — tier {job.tier}",
        )
    except InsufficientCreditsError:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Required: {credits}",
        )

    # 4. Set credits and generate upload URLs
    job.credits_charged = credits
    storage = _get_sim_data_storage(request)
    upload_urls = storage.generate_upload_urls(job_id=job.id)

    # 5. Dispatch to Celery
    try:
        task_result = run_simulation_task.delay(
            job_id=job.id,
            user_id=user_id,
            seed_text=job.seed_text,
            goal=job.goal,
            tier=job.tier,
            model_id=routing.model_id,
            gpu_type=routing.gpu_type,
            max_rounds=routing.max_rounds,
            vllm_args=routing.vllm_args or "",
            llm_api_key=os.getenv("LLM_API_KEY", "not-needed"),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            credits_charged=credits,
            enrich_web=job.enrich_web,
            forecast_days=job.forecast_days,
            target_agents=routing.target_agents,
            upload_urls=upload_urls,
        )
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to queue simulation job")

    # 6. Transition to PENDING
    job.celery_task_id = task_result.id
    job.status = JobStatus.PENDING
    await session.commit()
    await session.refresh(job)
    return job
