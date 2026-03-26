from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, field_validator


class TierEnum(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


TIER_CREDITS = {
    TierEnum.SMALL: 30,
    TierEnum.MEDIUM: 90,
    TierEnum.LARGE: 300,
}


class JobCreate(BaseModel):
    user_id: str
    seed_text: str
    goal: str
    tier: TierEnum

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
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
