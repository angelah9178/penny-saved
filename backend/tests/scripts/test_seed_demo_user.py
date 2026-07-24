"""Integration tests for the deterministic demo user."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.scripts.seed_demo import (
    DEMO_USER_EMAIL,
    DEMO_USER_ID,
    DEMO_USER_PASSWORD,
    SeedSafetyError,
    reconcile_demo_user,
)
from sqlalchemy import Connection, func, select


def test_demo_user_is_created_with_stable_identity_and_secure_hash(
    seed_connection: Connection,
) -> None:
    seeded_at = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)

    reconcile_demo_user(seed_connection, seeded_at=seeded_at)

    user = (
        seed_connection.execute(select(User.__table__).where(User.id == DEMO_USER_ID))
        .mappings()
        .one()
    )
    assert user["email"] == DEMO_USER_EMAIL
    assert user["created_at"] == seeded_at
    assert user["updated_at"] == seeded_at
    assert user["password_hash"] != DEMO_USER_PASSWORD
    assert DEMO_USER_PASSWORD not in user["password_hash"]
    assert verify_password(DEMO_USER_PASSWORD, user["password_hash"])


def test_repeated_seed_preserves_one_user_hash_and_timestamps(
    seed_connection: Connection,
) -> None:
    first_time = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    reconcile_demo_user(seed_connection, seeded_at=first_time)
    first = seed_connection.execute(select(User.__table__)).mappings().one()

    reconcile_demo_user(
        seed_connection,
        seeded_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
    )
    second = seed_connection.execute(select(User.__table__)).mappings().one()

    assert seed_connection.scalar(select(func.count()).select_from(User)) == 1
    assert second["password_hash"] == first["password_hash"]
    assert second["created_at"] == first["created_at"]
    assert second["updated_at"] == first["updated_at"]


def test_invalid_demo_hash_is_replaced(seed_connection: Connection) -> None:
    seeded_at = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    stale_hash = "not-a-password-hash"
    seed_connection.execute(
        User.__table__.insert().values(
            id=DEMO_USER_ID,
            email=DEMO_USER_EMAIL,
            password_hash=stale_hash,
            created_at=seeded_at,
            updated_at=seeded_at,
        )
    )
    replacement_time = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)

    reconcile_demo_user(seed_connection, seeded_at=replacement_time)

    user = seed_connection.execute(select(User.__table__)).mappings().one()
    assert user["password_hash"] != stale_hash
    assert verify_password(DEMO_USER_PASSWORD, user["password_hash"])
    assert user["created_at"] == seeded_at
    assert user["updated_at"] == replacement_time


@pytest.mark.parametrize("collision_field", ["id", "email"])
def test_demo_identity_collision_is_rejected(
    seed_connection: Connection,
    collision_field: str,
) -> None:
    values = {
        "id": DEMO_USER_ID if collision_field == "id" else "11111111-1111-4111-8111-111111111111",
        "email": DEMO_USER_EMAIL if collision_field == "email" else "other@example.local",
        "password_hash": hash_password("unrelated-password"),
        "created_at": datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 7, 24, 12, 0, tzinfo=UTC),
    }
    seed_connection.execute(User.__table__.insert().values(**values))

    with pytest.raises(SeedSafetyError, match="unrelated user"):
        reconcile_demo_user(
            seed_connection,
            seeded_at=datetime(2026, 7, 25, 12, 0, tzinfo=UTC),
        )

    assert seed_connection.scalar(select(func.count()).select_from(User)) == 1
