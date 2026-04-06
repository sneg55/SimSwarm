from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.dependencies import get_current_user
from saas.auth.service import hash_password, verify_password
from saas.database import get_session
from saas.auth.models import User

router = APIRouter(prefix="/profile", tags=["profile"])


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("/password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters")

    user_id = int(current_user["user_id"])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = hash_password(body.new_password)
    await session.commit()
    return {"status": "ok"}


@router.delete("/account")
async def delete_account(
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    user_id = int(current_user["user_id"])
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user.email = f"deleted_{user_id}@deleted"
    user.password_hash = ""
    await session.commit()
    return {"status": "deleted"}
