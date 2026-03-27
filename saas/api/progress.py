from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import json

from saas.database import get_session
from saas.models.job import SimulationJob
from saas.auth.dependencies import get_current_user

router = APIRouter(prefix="/jobs", tags=["progress"])


@router.get("/{job_id}/progress")
async def job_progress_stream(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """SSE stream for real-time job progress updates."""
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404)
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403)

    async def event_generator():
        while True:
            await session.refresh(job)
            data = {
                "status": job.status.value if hasattr(job.status, "value") else str(job.status),
                "pipeline_stage": job.pipeline_stage,
            }
            yield f"data: {json.dumps(data)}\n\n"

            if job.status.value in ("completed", "failed", "refunded"):
                break
            await asyncio.sleep(3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
