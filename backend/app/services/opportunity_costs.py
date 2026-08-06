"""Opportunity-cost example creation and listing workflows."""

from __future__ import annotations

from uuid import UUID

from app.api.errors import ApplicationError
from app.core.time import Clock, normalize_utc
from app.models.user import User
from app.repositories.opportunity_costs import (
    add_opportunity_cost_example,
    delete_owned_opportunity_cost_example,
    get_opportunity_cost_example_for_update,
    list_opportunity_cost_examples_by_user,
    opportunity_cost_example_id_exists,
    update_owned_opportunity_cost_example,
)
from app.schemas.opportunity_cost import (
    OpportunityCostCreateRequest,
    OpportunityCostExampleResponse,
    OpportunityCostExamplesResponse,
    OpportunityCostUpdateRequest,
    to_opportunity_cost_response,
)
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

EXAMPLE_NOT_FOUND_MESSAGE = "Opportunity-cost example not found."
EXAMPLE_FORBIDDEN_MESSAGE = "You do not have access to this opportunity-cost example."


async def create_opportunity_cost_example(
    db: AsyncSession,
    *,
    user: User,
    payload: OpportunityCostCreateRequest,
    clock: Clock,
) -> OpportunityCostExampleResponse:
    """Create and commit one example owned by the authenticated user."""
    try:
        now = normalize_utc(clock.now())
        example = add_opportunity_cost_example(
            db,
            user_id=user.id,
            label=payload.label,
            unit_name=payload.unit_name,
            dollar_value_cents=payload.dollar_value_cents,
            created_at=now,
        )
        await db.commit()
        return to_opportunity_cost_response(example)
    except BaseException:
        await db.rollback()
        raise


async def list_opportunity_cost_examples(
    db: AsyncSession,
    *,
    user: User,
) -> OpportunityCostExamplesResponse:
    """Return the authenticated user's examples in repository order."""
    examples = await list_opportunity_cost_examples_by_user(db, user_id=user.id)
    return OpportunityCostExamplesResponse(
        examples=[to_opportunity_cost_response(example) for example in examples]
    )


async def update_opportunity_cost_example(
    db: AsyncSession,
    *,
    user: User,
    example_id: UUID,
    payload: OpportunityCostUpdateRequest,
    clock: Clock,
) -> OpportunityCostExampleResponse:
    """Lock, update, and commit one example owned by the authenticated user."""
    try:
        example = await get_opportunity_cost_example_for_update(
            db,
            user_id=user.id,
            example_id=example_id,
        )
        if example is None:
            await _raise_example_access_error(db, example_id=example_id)

        now = normalize_utc(clock.now())
        update_owned_opportunity_cost_example(
            example=example,
            user_id=user.id,
            label=payload.label,
            unit_name=payload.unit_name,
            dollar_value_cents=payload.dollar_value_cents,
            updated_at=now,
        )
        await db.commit()
        return to_opportunity_cost_response(example)
    except BaseException:
        await db.rollback()
        raise


async def delete_opportunity_cost_example(
    db: AsyncSession,
    *,
    user: User,
    example_id: UUID,
) -> None:
    """Lock, delete, and commit one example owned by the authenticated user."""
    try:
        example = await get_opportunity_cost_example_for_update(
            db,
            user_id=user.id,
            example_id=example_id,
        )
        if example is None:
            await _raise_example_access_error(db, example_id=example_id)

        await delete_owned_opportunity_cost_example(
            db,
            example=example,
            user_id=user.id,
        )
        await db.commit()
    except BaseException:
        await db.rollback()
        raise


async def _raise_example_access_error(db: AsyncSession, *, example_id: UUID) -> None:
    if await opportunity_cost_example_id_exists(db, example_id=example_id):
        raise ApplicationError(
            status_code=status.HTTP_403_FORBIDDEN,
            code="forbidden",
            message=EXAMPLE_FORBIDDEN_MESSAGE,
        )
    raise ApplicationError(
        status_code=status.HTTP_404_NOT_FOUND,
        code="not_found",
        message=EXAMPLE_NOT_FOUND_MESSAGE,
    )
