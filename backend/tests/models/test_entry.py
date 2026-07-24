"""Metadata tests for the impulse-purchase entry model."""

from __future__ import annotations

from app.db.base import Base
from app.models import EntryStatus, ImpulsePurchaseEntry, User
from app.models.entry import MAX_PRICE_CENTS
from sqlalchemy import BigInteger, CheckConstraint, Enum
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID


def test_entry_table_is_registered_with_expected_columns() -> None:
    table = ImpulsePurchaseEntry.__table__

    assert table.name == "impulse_purchase_entries"
    assert Base.metadata.tables["impulse_purchase_entries"] is table
    assert list(table.columns.keys()) == [
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
    ]
    assert "needs_check_in" not in table.columns


def test_entry_columns_preserve_types_lengths_and_nullability() -> None:
    table = ImpulsePurchaseEntry.__table__

    assert isinstance(table.c.id.type, PostgreSQLUUID)
    assert table.c.id.type.as_uuid is True
    assert table.c.id.default is not None
    assert table.c.id.default.is_callable is True
    assert table.c.id.default.arg.__name__ == "uuid4"
    assert isinstance(table.c.user_id.type, PostgreSQLUUID)

    assert table.c.item_name.type.length == 200
    assert isinstance(table.c.price_cents.type, BigInteger)
    assert table.c.reason_wanted.type.length == 2000
    assert table.c.comment.type.length == 4000
    assert table.c.comment.nullable is True

    for name in ("created_at", "checked_in_at", "updated_at"):
        assert table.c[name].type.timezone is True
        assert table.c[name].default is None
        assert table.c[name].server_default is None

    assert table.c.created_at.nullable is False
    assert table.c.checked_in_at.nullable is True
    assert table.c.updated_at.nullable is False


def test_entry_status_uses_python_enum_and_bounded_varchar() -> None:
    status_type = ImpulsePurchaseEntry.__table__.c.status.type

    assert list(EntryStatus) == [
        EntryStatus.WAITING,
        EntryStatus.SAVED,
        EntryStatus.PURCHASED,
    ]
    assert [status.value for status in EntryStatus] == ["waiting", "saved", "purchased"]
    assert isinstance(status_type, Enum)
    assert status_type.enum_class is EntryStatus
    assert status_type.native_enum is False
    assert status_type.create_constraint is False
    assert status_type.length == 16
    assert status_type.enums == ["waiting", "saved", "purchased"]


def test_entry_has_named_ownership_and_lifecycle_constraints() -> None:
    table = ImpulsePurchaseEntry.__table__
    foreign_key = next(iter(table.foreign_key_constraints))
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert table.primary_key.name == "pk_impulse_purchase_entries"
    assert foreign_key.name == "fk_entries_user_id_users"
    assert foreign_key.referred_table is User.__table__
    assert foreign_key.ondelete == "CASCADE"
    assert checks == {
        "ck_entries_status": "status IN ('waiting', 'saved', 'purchased')",
        "ck_entries_item_name_not_blank": "length(btrim(item_name)) > 0",
        "ck_entries_reason_not_blank": "length(btrim(reason_wanted)) > 0",
        "ck_entries_comment_not_blank": ("comment IS NULL OR length(btrim(comment)) > 0"),
        "ck_entries_price": (f"price_cents BETWEEN 1 AND {MAX_PRICE_CENTS}"),
        "ck_entries_lifecycle": (
            "(status = 'waiting' AND checked_in_at IS NULL) "
            "OR (status IN ('saved', 'purchased') AND checked_in_at IS NOT NULL)"
        ),
        "ck_entries_checked_after_created": (
            "checked_in_at IS NULL OR checked_in_at >= created_at"
        ),
        "ck_entries_updated_after_created": "updated_at >= created_at",
    }


def test_entry_indexes_support_dashboard_and_statistics_ordering() -> None:
    indexes = {index.name: index for index in ImpulsePurchaseEntry.__table__.indexes}
    created_index = indexes["ix_entries_user_status_created"]
    checked_index = indexes["ix_entries_user_status_checked"]

    assert [expression.name for expression in created_index.expressions[:2]] == [
        "user_id",
        "status",
    ]
    assert created_index.expressions[-1].element.name == "created_at"
    assert [expression.name for expression in checked_index.expressions[:2]] == [
        "user_id",
        "status",
    ]
    assert checked_index.expressions[-1].element.name == "checked_in_at"
    assert str(created_index.expressions[-1]).endswith("created_at DESC")
    assert str(checked_index.expressions[-1]).endswith("checked_in_at DESC")


def test_entry_relationships_enforce_owned_explicit_loading() -> None:
    user_relationship = User.__mapper__.relationships["entries"]
    entry_relationship = ImpulsePurchaseEntry.__mapper__.relationships["user"]

    assert user_relationship.back_populates == "user"
    assert user_relationship.lazy == "raise"
    assert user_relationship.passive_deletes is True
    assert "delete-orphan" in user_relationship.cascade

    assert entry_relationship.back_populates == "entries"
    assert entry_relationship.lazy == "raise"
