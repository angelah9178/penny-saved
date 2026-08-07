"""PostgreSQL enforcement tests for the initial application schema."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.models import ImpulsePurchaseEntry, OpportunityCostExample, Session, User
from sqlalchemy import Connection, insert, inspect
from sqlalchemy.exc import IntegrityError

NOW = datetime(2026, 7, 24, 12, tzinfo=UTC)
VALID_TOKEN_HASH = "a" * 64


def _user_values(**overrides: Any) -> dict[str, Any]:
    values = {
        "id": uuid4(),
        "email": f"{uuid4()}@example.com",
        "password_hash": "argon2id-hash",
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return values


def _session_values(user_id: UUID, **overrides: Any) -> dict[str, Any]:
    values = {
        "id": uuid4(),
        "user_id": user_id,
        "session_token_hash": uuid4().hex * 2,
        "expires_at": NOW + timedelta(days=30),
        "created_at": NOW,
        "last_used_at": NOW,
    }
    values.update(overrides)
    return values


def _entry_values(user_id: UUID, **overrides: Any) -> dict[str, Any]:
    values = {
        "id": uuid4(),
        "user_id": user_id,
        "item_name": "Headphones",
        "price_cents": 12_500,
        "reason_wanted": "Useful for focused work",
        "status": "waiting",
        "comment": None,
        "created_at": NOW,
        "checked_in_at": None,
        "updated_at": NOW,
    }
    values.update(overrides)
    return values


def _example_values(user_id: UUID, **overrides: Any) -> dict[str, Any]:
    values = {
        "id": uuid4(),
        "user_id": user_id,
        "label": "Coffee",
        "unit_name": "cups",
        "dollar_value_cents": 500,
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return values


def _insert_user(connection: Connection) -> UUID:
    values = _user_values()
    connection.execute(insert(User), values)
    return values["id"]


def _assert_rejected(
    connection: Connection,
    model: type[Any],
    values: Mapping[str, Any],
) -> None:
    with pytest.raises(IntegrityError), connection.begin_nested():
        connection.execute(insert(model), values)


def test_migrated_schema_has_expected_tables_columns_constraints_and_indexes(
    db_connection: Connection,
) -> None:
    inspector = inspect(db_connection)
    expected_columns = {
        "users": {"id", "email", "password_hash", "created_at", "updated_at"},
        "sessions": {
            "id",
            "user_id",
            "session_token_hash",
            "expires_at",
            "created_at",
            "last_used_at",
        },
        "impulse_purchase_entries": {
            "id",
            "user_id",
            "item_name",
            "price_cents",
            "reason_wanted",
            "status",
            "comment",
            "created_at",
            "checked_in_at",
            "updated_at",
        },
        "opportunity_cost_examples": {
            "id",
            "user_id",
            "label",
            "unit_name",
            "dollar_value_cents",
            "created_at",
            "updated_at",
        },
        "rate_limit_counters": {
            "bucket",
            "key_digest",
            "attempt_count",
            "window_started_at",
            "expires_at",
        },
    }
    expected_primary_keys = {
        "users": "pk_users",
        "sessions": "pk_sessions",
        "impulse_purchase_entries": "pk_impulse_purchase_entries",
        "opportunity_cost_examples": "pk_opportunity_cost_examples",
        "rate_limit_counters": "pk_rate_limit_counters",
    }
    expected_foreign_keys = {
        "users": set(),
        "sessions": {"fk_sessions_user_id_users"},
        "impulse_purchase_entries": {"fk_entries_user_id_users"},
        "opportunity_cost_examples": {"fk_opportunity_cost_examples_user_id_users"},
        "rate_limit_counters": set(),
    }
    expected_indexes = {
        "users": {"uq_users_email"},
        "sessions": {
            "ix_sessions_expires_at",
            "ix_sessions_user_id",
            "uq_sessions_token_hash",
        },
        "impulse_purchase_entries": {
            "ix_entries_user_status_checked",
            "ix_entries_user_status_created",
        },
        "opportunity_cost_examples": {"ix_opportunity_cost_examples_user_created"},
        "rate_limit_counters": {"ix_rate_limit_counters_expires_at"},
    }

    assert set(inspector.get_table_names()) == {
        "alembic_version",
        *expected_columns,
    }
    for table_name, column_names in expected_columns.items():
        assert {column["name"] for column in inspector.get_columns(table_name)} == column_names
        assert inspector.get_pk_constraint(table_name)["name"] == expected_primary_keys[table_name]
        assert {
            foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name)
        } == expected_foreign_keys[table_name]
        assert {index["name"] for index in inspector.get_indexes(table_name)} == expected_indexes[
            table_name
        ]

    assert {constraint["name"] for constraint in inspector.get_check_constraints("users")} == {
        "ck_users_email_not_blank"
    }
    assert {constraint["name"] for constraint in inspector.get_check_constraints("sessions")} == {
        "ck_sessions_expiry",
        "ck_sessions_last_used",
        "ck_sessions_token_hash_format",
    }
    assert {
        constraint["name"]
        for constraint in inspector.get_check_constraints("impulse_purchase_entries")
    } == {
        "ck_entries_checked_after_created",
        "ck_entries_comment_not_blank",
        "ck_entries_item_name_not_blank",
        "ck_entries_lifecycle",
        "ck_entries_price",
        "ck_entries_reason_not_blank",
        "ck_entries_status",
        "ck_entries_updated_after_created",
    }
    assert {
        constraint["name"] for constraint in inspector.get_check_constraints("rate_limit_counters")
    } == {
        "ck_rate_limit_counters_attempt_count_positive",
        "ck_rate_limit_counters_bucket_not_blank",
        "ck_rate_limit_counters_key_digest_format",
        "ck_rate_limit_counters_window_expiry",
    }
    assert {
        constraint["name"]
        for constraint in inspector.get_check_constraints("opportunity_cost_examples")
    } == {
        "ck_opportunity_cost_examples_dollar_value",
        "ck_opportunity_cost_examples_label_not_blank",
        "ck_opportunity_cost_examples_unit_name_not_blank",
        "ck_opportunity_cost_examples_updated_after_created",
    }


def test_unique_email_and_session_token_hash_are_enforced(
    db_connection: Connection,
) -> None:
    user = _user_values(email="same@example.com")
    db_connection.execute(insert(User), user)
    _assert_rejected(
        db_connection,
        User,
        _user_values(email=user["email"]),
    )

    session = _session_values(user["id"], session_token_hash=VALID_TOKEN_HASH)
    db_connection.execute(insert(Session), session)
    _assert_rejected(
        db_connection,
        Session,
        _session_values(user["id"], session_token_hash=VALID_TOKEN_HASH),
    )


@pytest.mark.parametrize("email", ["", " "])
def test_blank_user_email_is_rejected(
    db_connection: Connection,
    email: str,
) -> None:
    _assert_rejected(db_connection, User, _user_values(email=email))


@pytest.mark.parametrize(
    ("overrides"),
    [
        {"session_token_hash": "not-a-sha256-digest"},
        {"expires_at": NOW},
        {"expires_at": NOW - timedelta(seconds=1)},
        {"last_used_at": NOW - timedelta(seconds=1)},
    ],
)
def test_invalid_session_values_are_rejected(
    db_connection: Connection,
    overrides: dict[str, Any],
) -> None:
    user_id = _insert_user(db_connection)
    _assert_rejected(
        db_connection,
        Session,
        _session_values(user_id, **overrides),
    )


@pytest.mark.parametrize(
    ("overrides"),
    [
        {"item_name": " "},
        {"reason_wanted": " "},
        {"comment": ""},
        {"price_cents": 0},
        {"price_cents": -1},
        {"price_cents": 1_000_000_000_000},
        {"status": "invalid"},
        {"status": "waiting", "checked_in_at": NOW},
        {"status": "saved", "checked_in_at": None},
        {"status": "purchased", "checked_in_at": None},
        {
            "status": "saved",
            "checked_in_at": NOW - timedelta(seconds=1),
        },
        {"updated_at": NOW - timedelta(seconds=1)},
    ],
)
def test_invalid_entry_values_are_rejected(
    db_connection: Connection,
    overrides: dict[str, Any],
) -> None:
    user_id = _insert_user(db_connection)
    _assert_rejected(
        db_connection,
        ImpulsePurchaseEntry,
        _entry_values(user_id, **overrides),
    )


@pytest.mark.parametrize(
    ("overrides"),
    [
        {"label": ""},
        {"unit_name": " "},
        {"dollar_value_cents": 0},
        {"dollar_value_cents": -1},
        {"dollar_value_cents": 1_000_000_000_000},
        {"updated_at": NOW - timedelta(seconds=1)},
    ],
)
def test_invalid_opportunity_cost_values_are_rejected(
    db_connection: Connection,
    overrides: dict[str, Any],
) -> None:
    user_id = _insert_user(db_connection)
    _assert_rejected(
        db_connection,
        OpportunityCostExample,
        _example_values(user_id, **overrides),
    )


def test_user_delete_cascades_to_all_owned_records(
    db_connection: Connection,
) -> None:
    user_id = _insert_user(db_connection)
    db_connection.execute(insert(Session), _session_values(user_id))
    db_connection.execute(insert(ImpulsePurchaseEntry), _entry_values(user_id))
    db_connection.execute(
        insert(OpportunityCostExample),
        _example_values(user_id),
    )

    db_connection.execute(User.__table__.delete().where(User.id == user_id))

    assert db_connection.execute(Session.__table__.select()).all() == []
    assert db_connection.execute(ImpulsePurchaseEntry.__table__.select()).all() == []
    assert db_connection.execute(OpportunityCostExample.__table__.select()).all() == []


def test_duplicate_opportunity_cost_labels_are_allowed(
    db_connection: Connection,
) -> None:
    user_id = _insert_user(db_connection)
    db_connection.execute(
        insert(OpportunityCostExample),
        [
            _example_values(user_id, label="Coffee", dollar_value_cents=500),
            _example_values(user_id, label="Coffee", dollar_value_cents=750),
        ],
    )

    rows = db_connection.execute(OpportunityCostExample.__table__.select()).all()
    assert len(rows) == 2
