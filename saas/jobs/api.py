import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.dependencies import get_current_user
from saas.database import get_session
from saas.jobs.api_draft import router as _draft_router
from saas.jobs.api_retry import router as _retry_router
from saas.jobs.api_share import router as _share_router
from saas.jobs.graph_adapter import adapt_graph_payload
from saas.jobs.models import JobStatus, ModelRouting, SimulationJob
from saas.jobs.schemas import JobCreate, JobListResponse, JobResponse
from saas.storage.minio_client import SimDataStorage
from saas.workflows.client import SIM_TASK_QUEUE, get_temporal_client
from saas.workflows.sim_workflow import SimulationWorkflow
from saas.workflows.types import SimParams

# Reject identical-payload resubmits inside this window to prevent UI
# double-click from launching the same sim twice.
_DUP_JOB_WINDOW_SECONDS = 60
_LIVE_JOB_STATUSES = (
    JobStatus.PENDING, JobStatus.PROVISIONING,
    JobStatus.RUNNING, JobStatus.REPORTING,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])
router.include_router(_share_router)
router.include_router(_draft_router)
router.include_router(_retry_router)


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


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    request: Request,
    body: JobCreate,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if request.app.state.settings.DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail="This is a read-only demo. Deploy your own instance to run simulations.",
        )
    max_seed_chars = request.app.state.settings.MAX_SEED_CHARS
    if len(body.seed_text) > max_seed_chars:
        raise HTTPException(
            status_code=400,
            detail=f"Seed text exceeds maximum of {max_seed_chars} characters",
        )

    user_id = current_user["user_id"]

    # Dedup: reject if the same user has an in-flight job with an identical
    # seed+goal+tier created within the dedup window. Catches UI double-click
    # and accidental client retries without launching the same sim twice.
    dup_cutoff = datetime.now(timezone.utc) - timedelta(seconds=_DUP_JOB_WINDOW_SECONDS)
    dup_q = select(SimulationJob.id).where(
        SimulationJob.user_id == user_id,
        SimulationJob.seed_text == body.seed_text,
        SimulationJob.goal == body.goal,
        SimulationJob.tier == body.tier.value,
        SimulationJob.status.in_(_LIVE_JOB_STATUSES),
        SimulationJob.created_at > dup_cutoff,
    )
    existing_dup = (await session.execute(dup_q)).scalar_one_or_none()
    if existing_dup is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate job — identical in-flight sim already running (job {existing_dup})",
        )

    # 1. Validate routing exists
    route = await session.execute(
        select(ModelRouting).where(ModelRouting.sim_tier == body.tier.value)
    )
    routing = route.scalar_one_or_none()
    if not routing:
        raise HTTPException(
            status_code=500,
            detail=f"No model routing configured for tier: {body.tier.value}",
        )

    # 2. Create job row (not committed yet)
    job = SimulationJob(
        user_id=user_id,
        seed_text=body.seed_text,
        goal=body.goal,
        tier=body.tier.value,
        status=JobStatus.PENDING,
        enrich_web=body.enrich_web,
        forecast_days=body.forecast_days,
    )
    session.add(job)
    await session.flush()  # get job.id without committing

    # Generate presigned upload URLs for rich simulation data
    storage = _get_sim_data_storage(request)
    upload_urls = storage.generate_upload_urls(job_id=job.id)

    # 3. Dispatch to Temporal
    sim_params = SimParams(
        job_id=job.id, user_id=user_id,
        seed_text=body.seed_text, goal=body.goal, tier=body.tier.value,
        model_id=routing.model_id, gpu_type=routing.gpu_type,
        max_rounds=routing.max_rounds, vllm_args=routing.vllm_args or "",
        llm_api_key=os.getenv("LLM_API_KEY", "not-needed"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        enrich_web=body.enrich_web,
        forecast_days=body.forecast_days,
        target_agents=routing.target_agents,
        upload_urls=upload_urls,
    )

    try:
        temporal_client = await get_temporal_client()
        handle = await temporal_client.start_workflow(
            SimulationWorkflow.run,
            sim_params,
            id=f"sim-{job.id}",
            task_queue=SIM_TASK_QUEUE,
        )
    except Exception:
        await session.rollback()
        raise HTTPException(status_code=500, detail="Failed to queue simulation job")

    # 4. Store workflow identity and commit
    job.workflow_id = handle.id
    job.workflow_run_id = handle.result_run_id
    await session.commit()
    await session.refresh(job)

    return job


@router.get("/{job_id}/sim-data")
async def get_sim_data(
    request: Request,
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return presigned download URLs for rich simulation data."""
    user_id = current_user["user_id"]
    result = await session.execute(
        select(SimulationJob).where(SimulationJob.id == job_id, SimulationJob.user_id == user_id)
    )
    job = result.scalar_one_or_none()
    if not job or not job.sim_data_available:
        raise HTTPException(status_code=404, detail="Simulation data not available")

    storage = _get_sim_data_storage(request)
    urls = storage.generate_download_urls(job_id=job_id)
    if not urls:
        raise HTTPException(status_code=404, detail="Object storage not configured")

    return {"job_id": job_id, "files": urls}


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
        raw = json.loads(job.result_graph)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=500, detail="Invalid graph data stored for this job")
    return JSONResponse(content=adapt_graph_payload(raw))


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


