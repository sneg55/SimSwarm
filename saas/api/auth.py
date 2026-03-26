import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.service import hash_password, verify_password, create_token
from saas.database import get_session
from saas.models.user import User
from saas.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _get_secret_key(request: Request) -> str:
    """Pull SECRET_KEY from app state (injected via create_app)."""
    return request.app.state.settings.SECRET_KEY


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    # Validate email format
    if not _EMAIL_RE.match(body.email):
        raise HTTPException(status_code=422, detail="Invalid email format")

    # Validate password length
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    # Check for duplicate email
    result = await session.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Create user
    user = User(email=body.email, password_hash=hash_password(body.password))
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token = create_token(user.id, user.email, _get_secret_key(request))
    return AuthResponse(user=UserInfo.model_validate(user), token=token)


@router.post("/login", response_model=AuthResponse, status_code=200)
async def login(
    body: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthResponse:
    # Look up user by email
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Verify password
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(user.id, user.email, _get_secret_key(request))
    return AuthResponse(user=UserInfo.model_validate(user), token=token)
