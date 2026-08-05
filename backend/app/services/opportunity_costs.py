"""Opportunity-cost example creation and listing workflows."""

from __future__ import annotations

from app.core.time import Clock, normalize_utc
from app.models.user import User
from app.repositories.opportunity_costs import (
    add_opportunity_cost_example,
    list_opportunity_cost_examples_by_user,
)
from app.schemas.opportunity_cost import (
    OpportunityCostCreateRequest,
    OpportunityCostExampleResponse,
    OpportunityCostExamplesResponse,
    to_opportunity_cost_response,
)
from sqlalchemy.ext.asyncio import AsyncSession


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
