"""Metadata tests for the login session persistence model."""

from __future__ import annotations

from app.db.base import Base
from app.models import Session, User
from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID


def test_session_table_is_registered_with_expected_columns() -> None:
    table = Session.__table__

    assert table.name == "sessions"
    assert Base.metadata.tables["sessions"] is table
    assert list(table.columns.keys()) == [
        "id",
        "user_id",
        "session_token_hash",
        "expires_at",
        "created_at",
        "last_used_at",
    ]


def test_session_columns_preserve_types_lengths_and_nullability() -> None:
    table = Session.__table__

    assert isinstance(table.c.id.type, PostgreSQLUUID)
    assert table.c.id.type.as_uuid is True
    assert table.c.id.primary_key is True
    assert table.c.id.default is not None
    assert table.c.id.default.is_callable is True
    assert table.c.id.default.arg.__name__ == "uuid4"

    assert isinstance(table.c.user_id.type, PostgreSQLUUID)
    assert table.c.user_id.nullable is False
    assert table.c.session_token_hash.type.length == 64
    assert table.c.session_token_hash.nullable is False

    for name in ("expires_at", "created_at", "last_used_at"):
        assert table.c[name].type.timezone is True
        assert table.c[name].nullable is False
        assert table.c[name].default is None
        assert table.c[name].server_default is None


def test_session_has_named_foreign_key_indexes_and_checks() -> None:
    table = Session.__table__
    foreign_key = next(iter(table.foreign_key_constraints))
    indexes = {index.name: index for index in table.indexes}
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert table.primary_key.name == "pk_sessions"
    assert foreign_key.name == "fk_sessions_user_id_users"
    assert foreign_key.referred_table is User.__table__
    assert foreign_key.ondelete == "CASCADE"

    assert indexes["uq_sessions_token_hash"].unique is True
    assert [column.name for column in indexes["uq_sessions_token_hash"].columns] == [
        "session_token_hash"
    ]
    assert [column.name for column in indexes["ix_sessions_user_id"].columns] == ["user_id"]
    assert [column.name for column in indexes["ix_sessions_expires_at"].columns] == ["expires_at"]

    assert checks == {
        "ck_sessions_token_hash_format": "session_token_hash ~ '^[0-9a-f]{64}$'",
        "ck_sessions_expiry": "expires_at > created_at",
        "ck_sessions_last_used": "last_used_at >= created_at",
    }


def test_session_relationships_enforce_owned_explicit_loading() -> None:
    user_relationship = User.__mapper__.relationships["sessions"]
    session_relationship = Session.__mapper__.relationships["user"]

    assert user_relationship.back_populates == "user"
    assert user_relationship.lazy == "raise"
    assert user_relationship.passive_deletes is True
    assert "delete-orphan" in user_relationship.cascade

    assert session_relationship.back_populates == "sessions"
    assert session_relationship.lazy == "raise"


def test_session_model_cannot_persist_raw_tokens_or_plaintext_passwords() -> None:
    persisted_names = set(Session.__table__.columns.keys())

    assert "session_token" not in persisted_names
    assert "raw_token" not in persisted_names
    assert "password" not in persisted_names
    assert "session_token_hash" in persisted_names
