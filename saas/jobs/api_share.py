"""Share link endpoints for simulation jobs."""
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.jobs.models import SimulationJob
from saas.auth.dependencies import get_current_user

router = APIRouter(tags=["jobs"])


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
