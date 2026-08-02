"""PostgreSQL integration tests for owned entry repository operations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from app.models.user import User
from app.repositories.entries import (
    add_entry,
    check_in_owned_entry,
    delete_owned_entry,
    entry_id_exists,
    get_entry_by_id,
    get_entry_for_update,
    list_entries_by_user,
    update_owned_entry_comment,
    update_owned_entry_details,
)
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

USER_ID = UUID("30000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("30000000-0000-4000-8000-000000000002")
WAITING_OLDER_ID = UUID("40000000-0000-4000-8000-000000000001")
WAITING_TIE_LOW_ID = UUID("40000000-0000-4000-8000-000000000002")
WAITING_TIE_HIGH_ID = UUID("40000000-0000-4000-8000-000000000003")
SAVED_LOW_ID = UUID("40000000-0000-4000-8000-000000000004")
SAVED_HIGH_ID = UUID("40000000-0000-4000-8000-000000000005")
PURCHASED_ID = UUID("40000000-0000-4000-8000-000000000006")
OTHER_ENTRY_ID = UUID("40000000-0000-4000-8000-000000000007")
UNKNOWN_ENTRY_ID = UUID("40000000-0000-4000-8000-000000000099")
NOW = datetime(2026, 7, 30, 12, tzinfo=UTC)


def make_entry(
    *,
    entry_id: UUID,
    user_id: UUID = USER_ID,
    status: EntryStatus = EntryStatus.WAITING,
    created_at: datetime = NOW,
    checked_in_at: datetime | None = None,
) -> ImpulsePurchaseEntry:
    return ImpulsePurchaseEntry(
        id=entry_id,
        user_id=user_id,
        item_name=f"Entry {entry_id}",
        price_cents=1_000,
        reason_wanted="Repository ownership test",
        status=status,
        comment=None,
        created_at=created_at,
        checked_in_at=checked_in_at,
        updated_at=checked_in_at or created_at,
    )


@pytest.fixture
async def db(test_database_url: URL) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(test_database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        await session.execute(ImpulsePurchaseEntry.__table__.delete())
        await session.execute(User.__table__.delete())
        session.add_all(
            [
                User(
                    id=USER_ID,
                    email="entry-owner@example.com",
                    password_hash="argon2-hash-placeholder",
                    created_at=NOW,
                    updated_at=NOW,
                ),
                User(
                    id=OTHER_USER_ID,
                    email="other-entry-owner@example.com",
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
            await session.execute(ImpulsePurchaseEntry.__table__.delete())
            await session.execute(User.__table__.delete())
            await session.commit()
    await engine.dispose()


@pytest.mark.asyncio
async def test_add_entry_stages_a_server_owned_waiting_entry_without_committing(
    db: AsyncSession,
) -> None:
    entry = add_entry(
        db,
        user_id=USER_ID,
        entry_id=WAITING_OLDER_ID,
        item_name="Headphones",
        price_cents=8_500,
        reason_wanted="Better noise cancellation",
        created_at=NOW,
    )

    assert entry.user_id == USER_ID
    assert entry.status is EntryStatus.WAITING
    assert entry.comment is None
    assert entry.checked_in_at is None
    assert entry.created_at == entry.updated_at == NOW
    assert inspect(entry).pending is True
    assert db.in_transaction() is True


@pytest.mark.asyncio
async def test_owned_reads_never_return_another_users_entry(db: AsyncSession) -> None:
    db.add(make_entry(entry_id=OTHER_ENTRY_ID, user_id=OTHER_USER_ID))
    await db.commit()

    assert await get_entry_by_id(db, user_id=USER_ID, entry_id=OTHER_ENTRY_ID) is None
    assert await get_entry_for_update(db, user_id=USER_ID, entry_id=OTHER_ENTRY_ID) is None
    assert await list_entries_by_user(db, user_id=USER_ID) == []

    owned = await get_entry_by_id(db, user_id=OTHER_USER_ID, entry_id=OTHER_ENTRY_ID)
    assert owned is not None
    assert owned.user_id == OTHER_USER_ID


@pytest.mark.asyncio
async def test_owned_lookup_returns_none_for_unknown_id(db: AsyncSession) -> None:
    assert await get_entry_by_id(db, user_id=USER_ID, entry_id=UNKNOWN_ENTRY_ID) is None
    assert await get_entry_for_update(db, user_id=USER_ID, entry_id=UNKNOWN_ENTRY_ID) is None


@pytest.mark.asyncio
async def test_get_entry_for_update_holds_the_database_row_lock(db: AsyncSession) -> None:
    db.add(make_entry(entry_id=WAITING_OLDER_ID))
    await db.commit()

    locked = await get_entry_for_update(
        db,
        user_id=USER_ID,
        entry_id=WAITING_OLDER_ID,
    )
    assert locked is not None

    competing_factory = async_sessionmaker(db.bind, expire_on_commit=False)
    async with competing_factory() as competing_db:
        await competing_db.execute(text("SET LOCAL lock_timeout = '100ms'"))
        with pytest.raises(DBAPIError):
            await get_entry_for_update(
                competing_db,
                user_id=USER_ID,
                entry_id=WAITING_OLDER_ID,
            )
        await competing_db.rollback()

    await db.rollback()


@pytest.mark.asyncio
async def test_existence_check_returns_only_boolean_without_loading_entry(
    db: AsyncSession,
) -> None:
    db.add(make_entry(entry_id=OTHER_ENTRY_ID, user_id=OTHER_USER_ID))
    await db.commit()
    db.expunge_all()

    assert await entry_id_exists(db, entry_id=OTHER_ENTRY_ID) is True
    assert await entry_id_exists(db, entry_id=UNKNOWN_ENTRY_ID) is False
    loaded_entries = [
        instance
        for instance in db.identity_map.values()
        if isinstance(instance, ImpulsePurchaseEntry)
    ]
    assert loaded_entries == []


@pytest.mark.asyncio
async def test_list_entries_uses_deterministic_per_bucket_order_and_excludes_other_users(
    db: AsyncSession,
) -> None:
    resolved_at = NOW - timedelta(hours=1)
    db.add_all(
        [
            make_entry(entry_id=WAITING_TIE_HIGH_ID, created_at=NOW - timedelta(hours=2)),
            make_entry(entry_id=WAITING_OLDER_ID, created_at=NOW - timedelta(hours=3)),
            make_entry(entry_id=WAITING_TIE_LOW_ID, created_at=NOW - timedelta(hours=2)),
            make_entry(
                entry_id=SAVED_LOW_ID,
                status=EntryStatus.SAVED,
                created_at=NOW - timedelta(days=3),
                checked_in_at=resolved_at,
            ),
            make_entry(
                entry_id=SAVED_HIGH_ID,
                status=EntryStatus.SAVED,
                created_at=NOW - timedelta(days=3),
                checked_in_at=resolved_at,
            ),
            make_entry(
                entry_id=PURCHASED_ID,
                status=EntryStatus.PURCHASED,
                created_at=NOW - timedelta(days=4),
                checked_in_at=NOW - timedelta(minutes=30),
            ),
            make_entry(entry_id=OTHER_ENTRY_ID, user_id=OTHER_USER_ID),
        ]
    )
    await db.commit()

    entries = await list_entries_by_user(db, user_id=USER_ID)
    waiting_ids = [entry.id for entry in entries if entry.status is EntryStatus.WAITING]
    saved_ids = [entry.id for entry in entries if entry.status is EntryStatus.SAVED]
    purchased_ids = [entry.id for entry in entries if entry.status is EntryStatus.PURCHASED]

    assert waiting_ids == [WAITING_OLDER_ID, WAITING_TIE_LOW_ID, WAITING_TIE_HIGH_ID]
    assert saved_ids == [SAVED_HIGH_ID, SAVED_LOW_ID]
    assert purchased_ids == [PURCHASED_ID]
    assert OTHER_ENTRY_ID not in [entry.id for entry in entries]


@pytest.mark.asyncio
async def test_update_helper_changes_only_owned_core_details(db: AsyncSession) -> None:
    entry = make_entry(entry_id=WAITING_OLDER_ID)
    db.add(entry)
    await db.commit()
    original_status = entry.status
    original_created_at = entry.created_at

    update_owned_entry_details(
        entry=entry,
        user_id=USER_ID,
        item_name="Updated headphones",
        price_cents=9_000,
        reason_wanted="Updated reason",
        updated_at=NOW + timedelta(minutes=1),
    )

    assert entry.item_name == "Updated headphones"
    assert entry.price_cents == 9_000
    assert entry.reason_wanted == "Updated reason"
    assert entry.updated_at == NOW + timedelta(minutes=1)
    assert entry.status is original_status
    assert entry.created_at == original_created_at
    assert inspect(entry).modified is True


def test_update_helper_rejects_an_entry_owned_by_another_user() -> None:
    entry = make_entry(entry_id=OTHER_ENTRY_ID, user_id=OTHER_USER_ID)

    with pytest.raises(ValueError, match="does not belong"):
        update_owned_entry_details(
            entry=entry,
            user_id=USER_ID,
            item_name="Forbidden update",
            price_cents=9_000,
            reason_wanted="Must not change",
            updated_at=NOW,
        )

    assert entry.item_name != "Forbidden update"


@pytest.mark.parametrize("result", [EntryStatus.SAVED, EntryStatus.PURCHASED])
def test_check_in_helper_changes_only_owned_resolution_fields(result: EntryStatus) -> None:
    entry = make_entry(entry_id=WAITING_OLDER_ID, created_at=NOW - timedelta(days=3))
    original_core_fields = (
        entry.id,
        entry.user_id,
        entry.item_name,
        entry.price_cents,
        entry.reason_wanted,
        entry.created_at,
    )
    checked_in_at = NOW + timedelta(minutes=1)

    check_in_owned_entry(
        entry=entry,
        user_id=USER_ID,
        result=result,
        comment="I made a decision.",
        checked_in_at=checked_in_at,
    )

    assert entry.status is result
    assert entry.comment == "I made a decision."
    assert entry.checked_in_at == checked_in_at
    assert entry.updated_at == checked_in_at
    assert (
        entry.id,
        entry.user_id,
        entry.item_name,
        entry.price_cents,
        entry.reason_wanted,
        entry.created_at,
    ) == original_core_fields
    assert inspect(entry).modified is True


def test_check_in_helper_rejects_an_entry_owned_by_another_user() -> None:
    entry = make_entry(entry_id=OTHER_ENTRY_ID, user_id=OTHER_USER_ID)
    original_values = dict(entry.__dict__)

    with pytest.raises(ValueError, match="does not belong"):
        check_in_owned_entry(
            entry=entry,
            user_id=USER_ID,
            result=EntryStatus.SAVED,
            comment="Forbidden decision",
            checked_in_at=NOW,
        )

    assert entry.__dict__ == original_values


def test_check_in_helper_rejects_waiting_as_a_result_without_mutation() -> None:
    entry = make_entry(entry_id=WAITING_OLDER_ID)
    original_values = dict(entry.__dict__)

    with pytest.raises(ValueError, match="must be saved or purchased"):
        check_in_owned_entry(
            entry=entry,
            user_id=USER_ID,
            result=EntryStatus.WAITING,
            comment="Not a resolved result",
            checked_in_at=NOW,
        )

    assert entry.__dict__ == original_values


@pytest.mark.parametrize("comment", ["Updated reflection", None])
def test_comment_update_helper_changes_only_owned_comment_metadata(
    comment: str | None,
) -> None:
    checked_in_at = NOW - timedelta(hours=1)
    entry = make_entry(
        entry_id=SAVED_LOW_ID,
        status=EntryStatus.SAVED,
        created_at=NOW - timedelta(days=3),
        checked_in_at=checked_in_at,
    )
    entry.comment = "Original reflection"
    original_protected_fields = (
        entry.id,
        entry.user_id,
        entry.item_name,
        entry.price_cents,
        entry.reason_wanted,
        entry.status,
        entry.created_at,
        entry.checked_in_at,
    )

    update_owned_entry_comment(
        entry=entry,
        user_id=USER_ID,
        comment=comment,
        updated_at=NOW,
    )

    assert entry.comment == comment
    assert entry.updated_at == NOW
    assert (
        entry.id,
        entry.user_id,
        entry.item_name,
        entry.price_cents,
        entry.reason_wanted,
        entry.status,
        entry.created_at,
        entry.checked_in_at,
    ) == original_protected_fields
    assert inspect(entry).modified is True


def test_comment_update_helper_rejects_an_entry_owned_by_another_user() -> None:
    entry = make_entry(
        entry_id=OTHER_ENTRY_ID,
        user_id=OTHER_USER_ID,
        status=EntryStatus.PURCHASED,
        checked_in_at=NOW - timedelta(hours=1),
    )
    original_values = dict(entry.__dict__)

    with pytest.raises(ValueError, match="does not belong"):
        update_owned_entry_comment(
            entry=entry,
            user_id=USER_ID,
            comment="Forbidden reflection",
            updated_at=NOW,
        )

    assert entry.__dict__ == original_values


@pytest.mark.asyncio
async def test_delete_helper_stages_only_owned_entry_deletion(db: AsyncSession) -> None:
    owned = make_entry(entry_id=WAITING_OLDER_ID)
    other = make_entry(entry_id=OTHER_ENTRY_ID, user_id=OTHER_USER_ID)
    db.add_all([owned, other])
    await db.commit()

    await delete_owned_entry(db, entry=owned, user_id=USER_ID)
    await db.flush()

    assert await db.get(ImpulsePurchaseEntry, WAITING_OLDER_ID) is None
    assert await db.get(ImpulsePurchaseEntry, OTHER_ENTRY_ID) is other


@pytest.mark.asyncio
async def test_delete_helper_rejects_an_entry_owned_by_another_user(db: AsyncSession) -> None:
    other = make_entry(entry_id=OTHER_ENTRY_ID, user_id=OTHER_USER_ID)
    db.add(other)
    await db.commit()

    with pytest.raises(ValueError, match="does not belong"):
        await delete_owned_entry(db, entry=other, user_id=USER_ID)

    assert (
        await db.scalar(
            select(ImpulsePurchaseEntry.id).where(ImpulsePurchaseEntry.id == OTHER_ENTRY_ID)
        )
        == OTHER_ENTRY_ID
    )
