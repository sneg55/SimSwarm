import io
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session
from saas.jobs.models import SimulationJob
from saas.auth.dependencies import get_current_user

router = APIRouter(prefix="/jobs", tags=["export"])


@router.get("/{job_id}/export/pdf")
async def export_pdf(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404)
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403)
    if not job.result_report:
        raise HTTPException(status_code=400, detail="No report available")

    pdf_bytes = markdown_to_pdf(job.result_report, job.goal)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=simulation-{job_id}.pdf"},
    )


@router.get("/{job_id}/export/json")
async def export_json(
    job_id: int,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    job = await session.get(SimulationJob, job_id)
    if not job:
        raise HTTPException(status_code=404)
    if job.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403)
    if not job.result_report:
        raise HTTPException(status_code=400, detail="No results available")

    import json
    export_data = {
        "job_id": job.id,
        "goal": job.goal,
        "tier": job.tier,
        "report": job.result_report,
        "chat_log": json.loads(job.result_chat_log) if job.result_chat_log else [],
        "graph": json.loads(job.result_graph) if job.result_graph else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
    return Response(
        content=json.dumps(export_data, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=simulation-{job_id}.json"},
    )


def markdown_to_pdf(markdown_text: str, title: str) -> bytes:
    """Convert markdown report to PDF using reportlab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.units import inch

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"], fontSize=18, spaceAfter=20
    )
    h2_style = ParagraphStyle(
        "CustomH2", parent=styles["Heading2"], fontSize=14, spaceAfter=10, spaceBefore=15
    )
    body_style = ParagraphStyle(
        "CustomBody", parent=styles["Normal"], fontSize=10, spaceAfter=8, leading=14
    )
    quote_style = ParagraphStyle(
        "Quote",
        parent=body_style,
        leftIndent=20,
        rightIndent=20,
        fontName="Helvetica-Oblique",
    )

    story = []
    story.append(Paragraph("SimSwarm Prediction Report", title_style))
    story.append(Paragraph(title, h2_style))
    story.append(Spacer(1, 20))

    for line in markdown_text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], h2_style))
        elif line.startswith("# "):
            story.append(Paragraph(line[2:], title_style))
        elif line.startswith("> "):
            text = line[2:].replace("&", "&amp;").replace("<", "&lt;")
            story.append(Paragraph(f'<i>"{text}"</i>', quote_style))
        elif line.startswith("- "):
            text = line[2:].replace("&", "&amp;").replace("<", "&lt;")
            story.append(Paragraph(f"• {text}", body_style))
        else:
            text = line.replace("&", "&amp;").replace("<", "&lt;")
            text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
            story.append(Paragraph(text, body_style))

    doc.build(story)
    return buffer.getvalue()
