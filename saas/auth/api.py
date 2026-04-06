import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from saas.auth.service import hash_password, verify_password, create_token
from saas.auth.email import generate_token, send_verification_email, send_password_reset_email
from saas.database import get_session
from saas.auth.models import User
from saas.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserInfo,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from saas.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

RESET_TOKEN_TTL_HOURS = 1


def _get_secret_key(request: Request) -> str:
    """Pull SECRET_KEY from app state (injected via create_app)."""
    return request.app.state.settings.SECRET_KEY


def _get_base_url(request: Request) -> str:
    """Derive base URL from the incoming request."""
    return str(request.base_url).rstrip("/")


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: RegisterRequest,
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

    # Generate verification token
    verification_token = generate_token()

    # Create user
    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        verification_token=verification_token,
        email_verified=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Send verification email (logs link for MVP)
    send_verification_email(user.email, verification_token, _get_base_url(request))

    token = create_token(user.id, user.email, _get_secret_key(request))
    return AuthResponse(user=UserInfo.model_validate(user), token=token)


@router.post("/login", response_model=AuthResponse, status_code=200)
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: LoginRequest,
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


@router.get("/verify")
async def verify_email(
    token: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.verification_token == token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token")
    user.email_verified = True
    user.verification_token = None
    await session.commit()
    return {"message": "Email verified successfully"}


@router.post("/forgot-password", status_code=200)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    # Always return 200 — don't reveal whether the email exists
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is not None:
        reset_token = generate_token()
        user.reset_token = reset_token
        user.reset_token_expires = datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_TTL_HOURS)
        await session.commit()
        send_password_reset_email(user.email, reset_token, _get_base_url(request))
    return {"message": "If that email is registered you will receive a reset link shortly"}


@router.post("/reset-password", status_code=200)
async def reset_password(
    body: ResetPasswordRequest,
    session: AsyncSession = Depends(get_session),
):
    if len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    result = await session.execute(select(User).where(User.reset_token == body.token))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    now = datetime.now(timezone.utc)
    expires = user.reset_token_expires
    # SQLite returns naive datetimes; treat them as UTC for comparison.
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires is None or expires < now:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user.password_hash = hash_password(body.password)
    user.reset_token = None
    user.reset_token_expires = None
    await session.commit()
    return {"message": "Password reset successfully"}
