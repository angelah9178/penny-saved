"""Integration tests for deterministic opportunity-cost examples."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.core.security import hash_password
from app.models.opportunity_cost_example import OpportunityCostExample
from app.models.user import User
from app.scripts.seed_demo import (
    DEMO_ENTRIES,
    DEMO_OPPORTUNITY_COSTS,
    DEMO_USER_ID,
    SeedSafetyError,
    reconcile_demo_opportunity_costs,
    reconcile_demo_user,
)
from sqlalchemy import Connection, func, select

NOW = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


def _saved_total_cents() -> int:
    return sum(entry.price_cents for entry in DEMO_ENTRIES if entry.status.value == "saved")


def test_examples_cover_whole_fractional_and_less_than_one_results(
    seed_connection: Connection,
) -> None:
    reconcile_demo_user(seed_connection, seeded_at=NOW)
    reconcile_demo_opportunity_costs(seed_connection, seeded_at=NOW)
    values = {
        row["label"]: row["dollar_value_cents"]
        for row in seed_connection.execute(select(OpportunityCostExample.__table__)).mappings()
    }
    saved_total = _saved_total_cents()

    assert values == {
        "Coffees": 500,
        "Movie tickets": 1_200,
        "Weekend trips": 125_000,
    }
    assert saved_total == 98_500
    assert saved_total % values["Coffees"] == 0
    assert saved_total % values["Movie tickets"] != 0
    assert saved_total / values["Movie tickets"] > 1
    assert saved_total / values["Weekend trips"] < 1


def test_repeated_seed_restores_examples_without_deleting_manual_rows(
    seed_connection: Connection,
) -> None:
    reconcile_demo_user(seed_connection, seeded_at=NOW)
    reconcile_demo_opportunity_costs(seed_connection, seeded_at=NOW)
    known_id = DEMO_OPPORTUNITY_COSTS[0].id
    deleted_id = DEMO_OPPORTUNITY_COSTS[1].id
    manual_id = UUID("50000000-0000-4000-8000-000000000001")
    seed_connection.execute(
        OpportunityCostExample.__table__.update()
        .where(OpportunityCostExample.id == known_id)
        .values(label="Changed locally")
    )
    seed_connection.execute(
        OpportunityCostExample.__table__.delete().where(OpportunityCostExample.id == deleted_id)
    )
    seed_connection.execute(
        OpportunityCostExample.__table__.insert().values(
            id=manual_id,
            user_id=DEMO_USER_ID,
            label="Manual comparison",
            unit_name="manual unit",
            dollar_value_cents=7_500,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    reconcile_demo_opportunity_costs(
        seed_connection,
        seeded_at=NOW + timedelta(days=1),
    )

    assert (
        seed_connection.scalar(select(func.count()).select_from(OpportunityCostExample))
        == len(DEMO_OPPORTUNITY_COSTS) + 1
    )
    restored = (
        seed_connection.execute(
            select(OpportunityCostExample.__table__).where(OpportunityCostExample.id == known_id)
        )
        .mappings()
        .one()
    )
    assert restored["label"] == DEMO_OPPORTUNITY_COSTS[0].label
    assert (
        seed_connection.scalar(
            select(func.count())
            .select_from(OpportunityCostExample)
            .where(OpportunityCostExample.id == deleted_id)
        )
        == 1
    )
    assert (
        seed_connection.scalar(
            select(func.count())
            .select_from(OpportunityCostExample)
            .where(OpportunityCostExample.id == manual_id)
        )
        == 1
    )


def test_opportunity_cost_id_owned_by_another_user_is_rejected(
    seed_connection: Connection,
) -> None:
    other_user_id = UUID("60000000-0000-4000-8000-000000000001")
    seed_connection.execute(
        User.__table__.insert().values(
            id=other_user_id,
            email="opportunity-owner@example.local",
            password_hash=hash_password("other-password"),
            created_at=NOW,
            updated_at=NOW,
        )
    )
    seed_connection.execute(
        OpportunityCostExample.__table__.insert().values(
            id=DEMO_OPPORTUNITY_COSTS[0].id,
            user_id=other_user_id,
            label="Unrelated comparison",
            unit_name="unrelated unit",
            dollar_value_cents=1_000,
            created_at=NOW,
            updated_at=NOW,
        )
    )

    with pytest.raises(SeedSafetyError, match="another user"):
        reconcile_demo_opportunity_costs(seed_connection, seeded_at=NOW)

    owner_id = seed_connection.scalar(
        select(OpportunityCostExample.user_id).where(
            OpportunityCostExample.id == DEMO_OPPORTUNITY_COSTS[0].id
        )
    )
    assert owner_id == other_user_id
