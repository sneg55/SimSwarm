from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from saas.database import get_session


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(session: AsyncSession = Depends(get_session)):
    try:
        await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return HealthResponse(status="ok", version="0.1.0", database=db_status)


class PublicConfig(BaseModel):
    demo_mode: bool


@router.get("/config", response_model=PublicConfig)
async def public_config(request: Request) -> PublicConfig:
    return PublicConfig(demo_mode=request.app.state.settings.DEMO_MODE)
