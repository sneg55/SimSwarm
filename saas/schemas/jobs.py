from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, field_validator


class TierEnum(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class JobCreate(BaseModel):
    seed_text: str
    goal: str
    tier: TierEnum
    enrich_web: bool = True
    forecast_days: int | None = None

    @field_validator("seed_text")
    @classmethod
    def seed_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("seed_text cannot be empty")
        return v


class JobResponse(BaseModel):
    id: int
    user_id: str
    seed_text: str
    goal: str
    tier: str
    credits_charged: int
    status: str
    pipeline_stage: int | None
    result_report: str | None = None
    result_chat_log: str | None = None
    error_message: str | None
    key_insight: str | None = None
    result_structured: str | None = None
    enriched_seed: str | None = None
    enrichment_citations: str | None = None
    enrich_web: bool = True
    sim_data_available: bool = False
    live_status: dict | None = None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobSummary(BaseModel):
    id: int
    goal: str
    tier: str
    credits_charged: int
    status: str
    pipeline_stage: int | None = None
    key_insight: str | None = None
    error_message: str | None = None
    enrich_web: bool = True
    enriched_seed: str | None = None
    sim_data_available: bool = False
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    jobs: list[JobSummary]
    total: int
    page: int
    per_page: int
