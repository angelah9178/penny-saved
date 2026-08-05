"""PostgreSQL integration tests for opportunity-cost repositories."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.models.opportunity_cost_example import OpportunityCostExample
from app.models.user import User
from app.repositories.opportunity_costs import (
    add_opportunity_cost_example,
    delete_owned_opportunity_cost_example,
    get_opportunity_cost_example_by_id,
    get_opportunity_cost_example_for_update,
    list_opportunity_cost_examples_by_user,
    opportunity_cost_example_id_exists,
    update_owned_opportunity_cost_example,
)
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

USER_ID = UUID("50000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("50000000-0000-4000-8000-000000000002")
OLDER_ID = UUID("60000000-0000-4000-8000-000000000001")
TIE_LOW_ID = UUID("60000000-0000-4000-8000-000000000002")
TIE_HIGH_ID = UUID("60000000-0000-4000-8000-000000000003")
OTHER_ID = UUID("60000000-0000-4000-8000-000000000004")
UNKNOWN_ID = UUID("60000000-0000-4000-8000-000000000099")
NOW = datetime(2026, 8, 5, 12, tzinfo=UTC)


def make_example(
    *,
    example_id: UUID,
    user_id: UUID = USER_ID,
    created_at: datetime = NOW,
    label: str = "Coffee",
) -> OpportunityCostExample:
    return OpportunityCostExample(
        id=example_id,
        user_id=user_id,
        label=label,
        unit_name="cups",
        dollar_value_cents=500,
        created_at=created_at,
        updated_at=created_at,
    )


@pytest.fixture
async def db(test_database_url: URL) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(OpportunityCostExample.__table__.delete())
        await session.execute(User.__table__.delete())
        session.add_all(
            [
                User(
                    id=USER_ID,
                    email="example-owner@example.com",
                    password_hash="argon2-hash-placeholder",
                    created_at=NOW,
                    updated_at=NOW,
                ),
                User(
                    id=OTHER_USER_ID,
                    email="other-example-owner@example.com",
                    password_hash="argon2-hash-placeholder",
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ]
        )
        await session.commit()
        try:
            yield session
        finally:
            await session.rollback()
            await session.execute(OpportunityCostExample.__table__.delete())
            await session.execute(User.__table__.delete())
            await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_add_stages_server_owned_example_without_committing(db: AsyncSession) -> None:
    example = add_opportunity_cost_example(
        db,
        user_id=USER_ID,
        example_id=OLDER_ID,
        label="Coffee",
        unit_name="cups",
        dollar_value_cents=500,
        created_at=NOW,
    )

    assert example.user_id == USER_ID
    assert example.created_at == example.updated_at == NOW
    assert inspect(example).pending is True
    assert db.in_transaction() is True


@pytest.mark.asyncio
async def test_owned_reads_exclude_other_users_and_unknown_ids(db: AsyncSession) -> None:
    db.add(make_example(example_id=OTHER_ID, user_id=OTHER_USER_ID))
    await db.commit()

    assert (
        await get_opportunity_cost_example_by_id(db, user_id=USER_ID, example_id=OTHER_ID) is None
    )
    assert (
        await get_opportunity_cost_example_for_update(db, user_id=USER_ID, example_id=OTHER_ID)
        is None
    )
    assert (
        await get_opportunity_cost_example_by_id(db, user_id=USER_ID, example_id=UNKNOWN_ID) is None
    )
    assert await list_opportunity_cost_examples_by_user(db, user_id=USER_ID) == []


@pytest.mark.asyncio
async def test_list_is_stable_allows_duplicate_labels_and_excludes_other_users(
    db: AsyncSession,
) -> None:
    db.add_all(
        [
            make_example(example_id=TIE_HIGH_ID, created_at=NOW, label="Coffee"),
            make_example(
                example_id=OLDER_ID,
                created_at=NOW - timedelta(days=1),
                label="Coffee",
            ),
            make_example(example_id=TIE_LOW_ID, created_at=NOW, label="Coffee"),
            make_example(example_id=OTHER_ID, user_id=OTHER_USER_ID),
        ]
    )
    await db.commit()

    examples = await list_opportunity_cost_examples_by_user(db, user_id=USER_ID)

    assert [example.id for example in examples] == [OLDER_ID, TIE_LOW_ID, TIE_HIGH_ID]
    assert [example.label for example in examples] == ["Coffee", "Coffee", "Coffee"]


@pytest.mark.asyncio
async def test_owned_lookup_holds_database_row_lock(db: AsyncSession) -> None:
    db.add(make_example(example_id=OLDER_ID))
    await db.commit()

    assert (
        await get_opportunity_cost_example_for_update(db, user_id=USER_ID, example_id=OLDER_ID)
        is not None
    )

    competing_factory = async_sessionmaker(db.bind, expire_on_commit=False)
    async with competing_factory() as competing_db:
        await competing_db.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(DBAPIError):
            await get_opportunity_cost_example_for_update(
                competing_db,
                user_id=USER_ID,
                example_id=OLDER_ID,
            )
        await competing_db.rollback()
    await db.rollback()


@pytest.mark.asyncio
async def test_existence_check_returns_boolean_without_loading_private_data(
    db: AsyncSession,
) -> None:
    db.add(make_example(example_id=OTHER_ID, user_id=OTHER_USER_ID))
    await db.commit()
    db.expunge_all()

    assert await opportunity_cost_example_id_exists(db, example_id=OTHER_ID) is True
    assert await opportunity_cost_example_id_exists(db, example_id=UNKNOWN_ID) is False
    assert not any(
        isinstance(instance, OpportunityCostExample) for instance in db.identity_map.values()
    )


def test_update_changes_only_mutable_fields_and_timestamp() -> None:
    example = make_example(example_id=OLDER_ID)
    protected = (example.id, example.user_id, example.created_at)

    update_owned_opportunity_cost_example(
        example=example,
        user_id=USER_ID,
        label="Lunch",
        unit_name="meals",
        dollar_value_cents=1_500,
        updated_at=NOW + timedelta(minutes=1),
    )

    assert (example.label, example.unit_name, example.dollar_value_cents) == (
        "Lunch",
        "meals",
        1_500,
    )
    assert example.updated_at == NOW + timedelta(minutes=1)
    assert (example.id, example.user_id, example.created_at) == protected


def test_update_rejects_other_owner_without_mutation() -> None:
    example = make_example(example_id=OTHER_ID, user_id=OTHER_USER_ID)
    original = dict(example.__dict__)

    with pytest.raises(ValueError, match="does not belong"):
        update_owned_opportunity_cost_example(
            example=example,
            user_id=USER_ID,
            label="Forbidden",
            unit_name="items",
            dollar_value_cents=1,
            updated_at=NOW,
        )
    assert example.__dict__ == original


@pytest.mark.asyncio
async def test_delete_stages_only_owned_example(db: AsyncSession) -> None:
    example = make_example(example_id=OLDER_ID)
    db.add(example)
    await db.commit()

    await delete_owned_opportunity_cost_example(db, example=example, user_id=USER_ID)

    assert example in db.deleted
    await db.rollback()
    assert (
        await db.scalar(select(OpportunityCostExample).where(OpportunityCostExample.id == OLDER_ID))
        is not None
    )


@pytest.mark.asyncio
async def test_delete_rejects_other_owner_without_staging(db: AsyncSession) -> None:
    example = make_example(example_id=OTHER_ID, user_id=OTHER_USER_ID)
    db.add(example)
    await db.commit()

    with pytest.raises(ValueError, match="does not belong"):
        await delete_owned_opportunity_cost_example(db, example=example, user_id=USER_ID)
    assert inspect(example).deleted is False
