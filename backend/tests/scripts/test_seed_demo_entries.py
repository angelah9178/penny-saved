"""Integration tests for deterministic representative demo entries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.core.security import hash_password
from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from app.models.user import User
from app.scripts.seed_demo import (
    DEMO_ENTRIES,
    DEMO_USER_ID,
    SeedSafetyError,
    reconcile_demo_entries,
    reconcile_demo_user,
)
from sqlalchemy import Connection, func, select

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def _seed_user_and_entries(connection: Connection) -> None:
    reconcile_demo_user(connection, seeded_at=NOW)
    reconcile_demo_entries(connection, seeded_at=NOW)


def test_demo_entries_cover_dashboard_states_and_48_hour_boundary(
    seed_connection: Connection,
) -> None:
    _seed_user_and_entries(seed_connection)
    rows = (
        seed_connection.execute(
            select(ImpulsePurchaseEntry.__table__).order_by(ImpulsePurchaseEntry.id)
        )
        .mappings()
        .all()
    )

    waiting = [row for row in rows if row["status"] == EntryStatus.WAITING]
    assert len(waiting) == 4
    assert sum(NOW - row["created_at"] < timedelta(hours=48) for row in waiting) == 2
    assert sum(NOW - row["created_at"] >= timedelta(hours=48) for row in waiting) == 2
    assert any(NOW - row["created_at"] == timedelta(hours=48) for row in waiting)
    assert all(row["checked_in_at"] is None for row in waiting)

    assert sum(row["status"] == EntryStatus.SAVED for row in rows) == 4
    assert sum(row["status"] == EntryStatus.PURCHASED for row in rows) == 1
    assert all(
        row["checked_in_at"] is not None for row in rows if row["status"] != EntryStatus.WAITING
    )


def test_demo_entries_cover_statistics_ranges_comments_and_prices(
    seed_connection: Connection,
) -> None:
    _seed_user_and_entries(seed_connection)
    rows = seed_connection.execute(select(ImpulsePurchaseEntry.__table__)).mappings().all()
    saved_ages = sorted(
        NOW - row["checked_in_at"] for row in rows if row["status"] == EntryStatus.SAVED
    )

    assert saved_ages == [
        timedelta(days=3),
        timedelta(days=21),
        timedelta(days=120),
        timedelta(days=500),
    ]
    assert any(row["comment"] is not None for row in rows if row["status"] == EntryStatus.SAVED)
    assert any(row["comment"] is None for row in rows if row["status"] == EntryStatus.SAVED)
    purchased = next(row for row in rows if row["status"] == EntryStatus.PURCHASED)
    assert purchased["comment"] is not None
    assert len({row["price_cents"] for row in rows}) == len(rows)
    assert all(row["price_cents"] > 0 for row in rows)


def test_repeated_seed_restores_known_entries_without_duplicates(
    seed_connection: Connection,
) -> None:
    _seed_user_and_entries(seed_connection)
    first_id = DEMO_ENTRIES[0].id
    seed_connection.execute(
        ImpulsePurchaseEntry.__table__.update()
        .where(ImpulsePurchaseEntry.id == first_id)
        .values(item_name="Locally changed name")
    )

    reconcile_demo_entries(
        seed_connection,
        seeded_at=NOW + timedelta(days=1),
    )

    assert seed_connection.scalar(select(func.count()).select_from(ImpulsePurchaseEntry)) == len(
        DEMO_ENTRIES
    )
    restored = (
        seed_connection.execute(
            select(ImpulsePurchaseEntry.__table__).where(ImpulsePurchaseEntry.id == first_id)
        )
        .mappings()
        .one()
    )
    assert restored["item_name"] == DEMO_ENTRIES[0].item_name
    assert restored["created_at"] == NOW + timedelta(days=1) - DEMO_ENTRIES[0].created_ago


def test_non_demo_entry_is_preserved(seed_connection: Connection) -> None:
    _seed_user_and_entries(seed_connection)
    manual_id = UUID("20000000-0000-4000-8000-000000000001")
    seed_connection.execute(
        ImpulsePurchaseEntry.__table__.insert().values(
            id=manual_id,
            user_id=DEMO_USER_ID,
            item_name="Manually entered item",
            price_cents=3_333,
            reason_wanted="Created outside the demo seed.",
            status=EntryStatus.WAITING,
            comment=None,
            created_at=NOW,
            checked_in_at=None,
            updated_at=NOW,
        )
    )

    reconcile_demo_entries(seed_connection, seeded_at=NOW + timedelta(days=1))

    assert (
        seed_connection.scalar(
            select(func.count())
            .select_from(ImpulsePurchaseEntry)
            .where(ImpulsePurchaseEntry.id == manual_id)
        )
        == 1
    )


def test_demo_entry_id_owned_by_another_user_is_rejected(
    seed_connection: Connection,
) -> None:
    other_user_id = UUID("30000000-0000-4000-8000-000000000001")
    seed_connection.execute(
        User.__table__.insert().values(
            id=other_user_id,
            email="other@example.local",
            password_hash=hash_password("other-password"),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    demo_entry = DEMO_ENTRIES[0]
    seed_connection.execute(
        ImpulsePurchaseEntry.__table__.insert().values(
            id=demo_entry.id,
            user_id=other_user_id,
            item_name="Unrelated owned entry",
            price_cents=1_000,
            reason_wanted="This row must not be taken over.",
            status=EntryStatus.WAITING,
            comment=None,
            created_at=NOW,
            checked_in_at=None,
            updated_at=NOW,
        )
    )

    with pytest.raises(SeedSafetyError, match="another user"):
        reconcile_demo_entries(seed_connection, seeded_at=NOW)

    owner_id = seed_connection.scalar(
        select(ImpulsePurchaseEntry.user_id).where(ImpulsePurchaseEntry.id == demo_entry.id)
    )
    assert owner_id == other_user_id
