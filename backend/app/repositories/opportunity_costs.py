"""Authenticated-user-scoped opportunity-cost persistence operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.models.opportunity_cost_example import OpportunityCostExample
from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession


def add_opportunity_cost_example(
    db: AsyncSession,
    *,
    user_id: UUID,
    label: str,
    unit_name: str,
    dollar_value_cents: int,
    created_at: datetime,
    example_id: UUID | None = None,
) -> OpportunityCostExample:
    """Stage a new example owned by the authenticated user."""
    example = OpportunityCostExample(
        id=example_id or uuid4(),
        user_id=user_id,
        label=label,
        unit_name=unit_name,
        dollar_value_cents=dollar_value_cents,
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(example)
    return example


async def list_opportunity_cost_examples_by_user(
    db: AsyncSession,
    *,
    user_id: UUID,
) -> list[OpportunityCostExample]:
    """Return only one user's examples in stable creation order."""
    statement = (
        select(OpportunityCostExample)
        .where(OpportunityCostExample.user_id == user_id)
        .order_by(
            OpportunityCostExample.created_at.asc(),
            OpportunityCostExample.id.asc(),
        )
    )
    return list((await db.scalars(statement)).all())


async def get_opportunity_cost_example_by_id(
    db: AsyncSession,
    *,
    user_id: UUID,
    example_id: UUID,
) -> OpportunityCostExample | None:
    """Return an example only when it belongs to the authenticated user."""
    statement = select(OpportunityCostExample).where(
        OpportunityCostExample.id == example_id,
        OpportunityCostExample.user_id == user_id,
    )
    return await db.scalar(statement)


async def get_opportunity_cost_example_for_update(
    db: AsyncSession,
    *,
    user_id: UUID,
    example_id: UUID,
) -> OpportunityCostExample | None:
    """Lock and return an example only when the user owns it."""
    statement = (
        select(OpportunityCostExample)
        .where(
            OpportunityCostExample.id == example_id,
            OpportunityCostExample.user_id == user_id,
        )
        .with_for_update()
    )
    return await db.scalar(statement)


async def opportunity_cost_example_id_exists(
    db: AsyncSession,
    *,
    example_id: UUID,
) -> bool:
    """Check ID existence without loading an example or its private fields."""
    statement = select(literal(True)).where(
        select(OpportunityCostExample.id).where(OpportunityCostExample.id == example_id).exists()
    )
    return bool(await db.scalar(statement))


def update_owned_opportunity_cost_example(
    *,
    example: OpportunityCostExample,
    user_id: UUID,
    label: str,
    unit_name: str,
    dollar_value_cents: int,
    updated_at: datetime,
) -> None:
    """Stage allowed field changes after an owned example has been locked."""
    _require_example_owner(example, user_id)
    example.label = label
    example.unit_name = unit_name
    example.dollar_value_cents = dollar_value_cents
    example.updated_at = updated_at


async def delete_owned_opportunity_cost_example(
    db: AsyncSession,
    *,
    example: OpportunityCostExample,
    user_id: UUID,
) -> None:
    """Stage deletion after an owned example has been locked."""
    _require_example_owner(example, user_id)
    await db.delete(example)


def _require_example_owner(example: OpportunityCostExample, user_id: UUID) -> None:
    if example.user_id != user_id:
        raise ValueError("opportunity-cost example does not belong to the authenticated user")
