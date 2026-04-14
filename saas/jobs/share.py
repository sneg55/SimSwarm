from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import json
import html as html_mod

from saas.database import get_session
from saas.jobs.graph_adapter import adapt_graph_payload
from saas.jobs.models import SimulationJob, JobStatus

router = APIRouter(prefix="/share", tags=["share"])

DEMO_USER_EMAIL = "demo@fishcloud.internal"


@router.get("/demos")
async def list_demos(session: AsyncSession = Depends(get_session)):
    """Return all shared demo results for the landing page."""
    user_result = await session.execute(
        text("SELECT id FROM users WHERE email = :email"),
        {"email": DEMO_USER_EMAIL},
    )
    user_row = user_result.first()
    if not user_row:
        return []

    result = await session.execute(
        select(SimulationJob).where(
            SimulationJob.user_id == str(user_row[0]),
            SimulationJob.share_token.is_not(None),
            SimulationJob.status == JobStatus.COMPLETED,
        ).order_by(SimulationJob.created_at.desc())
    )
    jobs = result.scalars().all()

    return [
        {
            "title": job.goal,
            "tier": job.tier,
            "share_token": job.share_token,
            "share_url": f"/s/{job.share_token}",
            "report_length": len(job.result_report or ""),
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
        for job in jobs
    ]


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

    chat_log = json.loads(job.result_chat_log) if job.result_chat_log else []
    graph_data = json.loads(job.result_graph) if job.result_graph else None

    return {
        "id": job.id,
        "goal": job.goal,
        "tier": job.tier,
        "title": job.goal,  # Use goal as title
        "report": job.result_report,
        "chat_log": chat_log,
        "graph": graph_data,
        "structured": json.loads(job.result_structured) if job.result_structured else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@router.get("/{token}/og", response_class=HTMLResponse)
async def get_shared_og_page(
    token: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Return an HTML page with OpenGraph meta tags for link previews."""
    result = await session.execute(
        select(SimulationJob).where(SimulationJob.share_token == token)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Shared result not found")

    title = html_mod.escape(job.goal or "SimSwarm Simulation")
    description = ""
    if job.key_insight:
        description = html_mod.escape(job.key_insight[:200])
    elif job.result_report:
        # First non-heading paragraph, max 200 chars
        for line in job.result_report.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and len(stripped) > 30:
                description = html_mod.escape(stripped[:200])
                break
    if not description:
        description = html_mod.escape(f"AI swarm simulation: {job.goal or ''}"[:200])

    canonical = f"https://simswarm.com/s/{token}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — SimSwarm</title>
<meta name="description" content="{description}">
<meta property="og:type" content="article">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="SimSwarm">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta http-equiv="refresh" content="0;url=/s/{token}">
</head>
<body>
<p>Redirecting to <a href="/s/{token}">SimSwarm results</a>...</p>
</body>
</html>"""


@router.get("/{token}/graph")
async def get_shared_graph(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(SimulationJob).where(SimulationJob.share_token == token)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Shared result not found")
    if not job.result_graph:
        raise HTTPException(status_code=404, detail="Graph data not available")
    try:
        raw = json.loads(job.result_graph)
    except (json.JSONDecodeError, TypeError):
        raise HTTPException(status_code=500, detail="Invalid graph data")
    return JSONResponse(content=adapt_graph_payload(raw))
