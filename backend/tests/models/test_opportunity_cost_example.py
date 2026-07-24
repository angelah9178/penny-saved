"""Metadata tests for the opportunity-cost example model."""

from __future__ import annotations

from app.db.base import Base
from app.models import OpportunityCostExample, User
from app.models.opportunity_cost_example import MAX_DOLLAR_VALUE_CENTS
from sqlalchemy import BigInteger, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID


def test_opportunity_cost_table_is_registered_with_expected_columns() -> None:
    table = OpportunityCostExample.__table__

    assert table.name == "opportunity_cost_examples"
    assert Base.metadata.tables["opportunity_cost_examples"] is table
    assert list(table.columns.keys()) == [
        "id",
        "user_id",
        "label",
        "unit_name",
        "dollar_value_cents",
        "created_at",
        "updated_at",
    ]


def test_opportunity_cost_columns_preserve_types_lengths_and_nullability() -> None:
    table = OpportunityCostExample.__table__

    assert isinstance(table.c.id.type, PostgreSQLUUID)
    assert table.c.id.type.as_uuid is True
    assert table.c.id.default is not None
    assert table.c.id.default.is_callable is True
    assert table.c.id.default.arg.__name__ == "uuid4"
    assert isinstance(table.c.user_id.type, PostgreSQLUUID)

    assert table.c.label.type.length == 120
    assert table.c.unit_name.type.length == 80
    assert isinstance(table.c.dollar_value_cents.type, BigInteger)

    for name in ("user_id", "label", "unit_name", "dollar_value_cents"):
        assert table.c[name].nullable is False

    for name in ("created_at", "updated_at"):
        assert table.c[name].type.timezone is True
        assert table.c[name].nullable is False
        assert table.c[name].default is None
        assert table.c[name].server_default is None


def test_opportunity_cost_has_named_ownership_and_value_constraints() -> None:
    table = OpportunityCostExample.__table__
    foreign_key = next(iter(table.foreign_key_constraints))
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert table.primary_key.name == "pk_opportunity_cost_examples"
    assert foreign_key.name == "fk_opportunity_cost_examples_user_id_users"
    assert foreign_key.referred_table is User.__table__
    assert foreign_key.ondelete == "CASCADE"
    assert checks == {
        "ck_opportunity_cost_examples_label_not_blank": "length(btrim(label)) > 0",
        "ck_opportunity_cost_examples_unit_name_not_blank": ("length(btrim(unit_name)) > 0"),
        "ck_opportunity_cost_examples_dollar_value": (
            f"dollar_value_cents BETWEEN 1 AND {MAX_DOLLAR_VALUE_CENTS}"
        ),
        "ck_opportunity_cost_examples_updated_after_created": ("updated_at >= created_at"),
    }


def test_opportunity_cost_index_provides_stable_listing_order() -> None:
    indexes = {index.name: index for index in OpportunityCostExample.__table__.indexes}
    listing_index = indexes["ix_opportunity_cost_examples_user_created"]

    assert [column.name for column in listing_index.columns] == [
        "user_id",
        "created_at",
        "id",
    ]
    assert listing_index.unique is False


def test_opportunity_cost_duplicate_labels_are_allowed() -> None:
    table = OpportunityCostExample.__table__
    unique_columns = {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    unique_indexes = {
        tuple(column.name for column in index.columns) for index in table.indexes if index.unique
    }

    assert ("label",) not in unique_columns
    assert ("label",) not in unique_indexes


def test_opportunity_cost_relationships_enforce_owned_explicit_loading() -> None:
    user_relationship = User.__mapper__.relationships["opportunity_cost_examples"]
    example_relationship = OpportunityCostExample.__mapper__.relationships["user"]

    assert user_relationship.back_populates == "user"
    assert user_relationship.lazy == "raise"
    assert user_relationship.passive_deletes is True
    assert "delete-orphan" in user_relationship.cascade

    assert example_relationship.back_populates == "opportunity_cost_examples"
    assert example_relationship.lazy == "raise"
