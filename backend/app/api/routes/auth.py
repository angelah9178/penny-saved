"""Authentication API routes."""

from __future__ import annotations

from typing import Annotated

from app.api.cookies import set_session_cookie
from app.core.config import Settings
from app.core.time import Clock, get_clock
from app.db.session import get_db_session
from app.schemas.auth import AuthRequest, AuthResponse, UserResponse
from app.schemas.common import ErrorResponse
from app.services.auth import login, signup
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/signup",
    operation_id="signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def signup_user(
    credentials: AuthRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> AuthResponse:
    """Create an account, issue its first session, and return the public user."""
    settings: Settings = request.app.state.settings
    result = await signup(
        db,
        credentials=credentials,
        clock=clock,
        settings=settings,
    )
    set_session_cookie(
        response,
        raw_token=result.issued_session.raw_token,
        settings=settings,
    )
    return AuthResponse(user=UserResponse.model_validate(result.user))


@router.post(
    "/login",
    operation_id="login",
    response_model=AuthResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
async def login_user(
    credentials: AuthRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> AuthResponse:
    """Verify credentials, issue a new session, and return the public user."""
    settings: Settings = request.app.state.settings
    result = await login(
        db,
        credentials=credentials,
        clock=clock,
        settings=settings,
    )
    set_session_cookie(
        response,
        raw_token=result.issued_session.raw_token,
        settings=settings,
    )
    return AuthResponse(user=UserResponse.model_validate(result.user))
