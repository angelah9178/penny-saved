"""Authenticated opportunity-cost example API routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from app.api.dependencies import enforce_trusted_origin, get_current_user
from app.core.time import Clock, get_clock
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.common import ErrorResponse
from app.schemas.opportunity_cost import (
    OpportunityCostCreateRequest,
    OpportunityCostExampleEnvelope,
    OpportunityCostExamplesResponse,
    OpportunityCostUpdateRequest,
)
from app.services.opportunity_costs import (
    create_opportunity_cost_example,
    delete_opportunity_cost_example,
    list_opportunity_cost_examples,
    update_opportunity_cost_example,
)
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/opportunity-cost-examples", tags=["opportunity-costs"])


@router.post(
    "",
    operation_id="create_opportunity_cost_example",
    response_model=OpportunityCostExampleEnvelope,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def create_user_opportunity_cost_example(
    payload: OpportunityCostCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    trusted_origin: Annotated[None, Depends(enforce_trusted_origin)],
) -> OpportunityCostExampleEnvelope:
    """Create an opportunity-cost example for the authenticated user."""
    del trusted_origin
    example = await create_opportunity_cost_example(
        db,
        user=user,
        payload=payload,
        clock=clock,
    )
    return OpportunityCostExampleEnvelope(example=example)


@router.get(
    "",
    operation_id="list_opportunity_cost_examples",
    response_model=OpportunityCostExamplesResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def list_user_opportunity_cost_examples(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> OpportunityCostExamplesResponse:
    """List the authenticated user's opportunity-cost examples."""
    return await list_opportunity_cost_examples(db, user=user)


@router.patch(
    "/{example_id}",
    operation_id="update_opportunity_cost_example",
    response_model=OpportunityCostExampleEnvelope,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def update_user_opportunity_cost_example(
    example_id: UUID,
    payload: OpportunityCostUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    trusted_origin: Annotated[None, Depends(enforce_trusted_origin)],
) -> OpportunityCostExampleEnvelope:
    """Update one opportunity-cost example owned by the authenticated user."""
    del trusted_origin
    example = await update_opportunity_cost_example(
        db,
        user=user,
        example_id=example_id,
        payload=payload,
        clock=clock,
    )
    return OpportunityCostExampleEnvelope(example=example)


@router.delete(
    "/{example_id}",
    operation_id="delete_opportunity_cost_example",
    response_class=Response,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ErrorResponse},
    },
)
async def delete_user_opportunity_cost_example(
    example_id: UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    trusted_origin: Annotated[None, Depends(enforce_trusted_origin)],
) -> Response:
    """Delete one opportunity-cost example owned by the authenticated user."""
    del trusted_origin
    await delete_opportunity_cost_example(db, user=user, example_id=example_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
