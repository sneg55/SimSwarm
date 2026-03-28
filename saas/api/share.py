from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from saas.database import get_session
from saas.models.job import SimulationJob

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/{token}")
async def get_shared_result(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(SimulationJob).where(SimulationJob.share_token == token)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Shared result not found")

    return {
        "goal": job.goal,
        "tier": job.tier,
        "report": job.result_report,
        "chat_log": json.loads(job.result_chat_log) if job.result_chat_log else [],
        "graph": json.loads(job.result_graph) if job.result_graph else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
