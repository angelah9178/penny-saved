"""Metadata tests for the user persistence model."""

from __future__ import annotations

from app.db.base import Base
from app.models import User
from sqlalchemy import CheckConstraint, Index, Text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID


def test_user_table_is_registered_with_expected_columns() -> None:
    table = User.__table__

    assert table.name == "users"
    assert Base.metadata.tables["users"] is table
    assert list(table.columns.keys()) == [
        "id",
        "email",
        "password_hash",
        "created_at",
        "updated_at",
    ]


def test_user_columns_preserve_types_lengths_and_nullability() -> None:
    table = User.__table__

    assert isinstance(table.c.id.type, PostgreSQLUUID)
    assert table.c.id.type.as_uuid is True
    assert table.c.id.primary_key is True
    assert table.c.id.nullable is False
    assert table.c.id.default is not None
    assert table.c.id.default.is_callable is True
    assert table.c.id.default.arg.__name__ == "uuid4"

    assert table.c.email.type.length == 320
    assert table.c.email.nullable is False
    assert isinstance(table.c.password_hash.type, Text)
    assert table.c.password_hash.nullable is False

    for name in ("created_at", "updated_at"):
        assert table.c[name].type.timezone is True
        assert table.c[name].nullable is False
        assert table.c[name].default is None
        assert table.c[name].server_default is None


def test_user_email_has_named_uniqueness_and_nonblank_rules() -> None:
    table = User.__table__
    email_index = next(
        index
        for index in table.indexes
        if isinstance(index, Index) and index.name == "uq_users_email"
    )
    email_check = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint) and constraint.name == "ck_users_email_not_blank"
    )

    assert email_index.unique is True
    assert [column.name for column in email_index.columns] == ["email"]
    assert str(email_check.sqltext) == "length(btrim(email)) > 0"
    assert table.primary_key.name == "pk_users"


def test_user_model_cannot_persist_plaintext_passwords() -> None:
    persisted_names = set(User.__table__.columns.keys())

    assert "password" not in persisted_names
    assert "plaintext_password" not in persisted_names
    assert "password_hash" in persisted_names
