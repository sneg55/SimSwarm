from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.models.job import SimulationJob, JobStatus
from saas.schemas.jobs import JobCreate, JobResponse, TIER_CREDITS
from saas.billing.ledger import CreditLedger, InsufficientCreditsError
from saas.auth.dependencies import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])

MAX_SEED_CHARS = 50_000


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    body: JobCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if len(body.seed_text) > MAX_SEED_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Seed text exceeds maximum of {MAX_SEED_CHARS} characters",
        )

    user_id = current_user["user_id"]
    credits = TIER_CREDITS[body.tier]

    # Check and deduct credits atomically
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

    job = SimulationJob(
        user_id=user_id,
        seed_text=body.seed_text,
        goal=body.goal,
        tier=body.tier.value,
        credits_charged=credits,
        status=JobStatus.PENDING,
    )
    session.add(job)
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


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = current_user["user_id"]
    result = await session.execute(
        select(SimulationJob)
        .where(SimulationJob.user_id == user_id)
        .order_by(SimulationJob.created_at.desc())
    )
    return result.scalars().all()
