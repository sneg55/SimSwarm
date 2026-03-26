from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BalanceResponse(BaseModel):
    user_id: str
    balance: int


class PurchaseRequest(BaseModel):
    user_id: str
    pack_id: str


class PurchaseResponse(BaseModel):
    session_id: str
    checkout_url: str


class CreditHistoryEntry(BaseModel):
    id: int
    user_id: str
    amount: int
    description: str
    stripe_session_id: str | None
    job_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}
