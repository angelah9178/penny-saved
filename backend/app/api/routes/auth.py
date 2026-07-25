"""Authentication API routes."""

from __future__ import annotations

from typing import Annotated

from app.api.cookies import clear_session_cookie, set_session_cookie
from app.api.dependencies import get_current_user, get_presented_session_token
from app.core.config import Settings
from app.core.time import Clock, get_clock
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.auth import AuthRequest, AuthResponse, UserResponse
from app.schemas.common import ErrorResponse
from app.services.auth import login, signup
from app.services.sessions import revoke_session
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


@router.get(
    "/me",
    operation_id="get_current_session",
    response_model=AuthResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
async def get_current_session(
    user: Annotated[User, Depends(get_current_user)],
) -> AuthResponse:
    """Return the public account represented by the current valid session."""
    return AuthResponse(user=UserResponse.model_validate(user))


@router.post(
    "/logout",
    operation_id="logout",
    response_class=Response,
)
async def logout_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Idempotently revoke the presented session and clear its browser cookie."""
    settings: Settings = request.app.state.settings
    raw_token = get_presented_session_token(request)
    if raw_token is not None:
        await revoke_session(db, raw_token=raw_token)

    response = Response(status_code=status.HTTP_200_OK)
    clear_session_cookie(response, settings=settings)
    return response
