"""Create the initial application schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create all initial tables, constraints, and indexes."""
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(btrim(email)) > 0",
            name=op.f("ck_users_email_not_blank"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )
    op.create_index("uq_users_email", "users", ["email"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_token_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "session_token_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_sessions_token_hash_format"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_sessions_expiry"),
        ),
        sa.CheckConstraint(
            "last_used_at >= created_at",
            name=op.f("ck_sessions_last_used"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sessions"),
    )
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"], unique=False)
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index(
        "uq_sessions_token_hash",
        "sessions",
        ["session_token_hash"],
        unique=True,
    )

    op.create_table(
        "impulse_purchase_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("price_cents", sa.BigInteger(), nullable=False),
        sa.Column("reason_wanted", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("comment", sa.String(length=4000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('waiting', 'saved', 'purchased')",
            name=op.f("ck_entries_status"),
        ),
        sa.CheckConstraint(
            "length(btrim(item_name)) > 0",
            name=op.f("ck_entries_item_name_not_blank"),
        ),
        sa.CheckConstraint(
            "length(btrim(reason_wanted)) > 0",
            name=op.f("ck_entries_reason_not_blank"),
        ),
        sa.CheckConstraint(
            "comment IS NULL OR length(btrim(comment)) > 0",
            name=op.f("ck_entries_comment_not_blank"),
        ),
        sa.CheckConstraint(
            "price_cents BETWEEN 1 AND 999999999999",
            name=op.f("ck_entries_price"),
        ),
        sa.CheckConstraint(
            "(status = 'waiting' AND checked_in_at IS NULL) "
            "OR (status IN ('saved', 'purchased') AND checked_in_at IS NOT NULL)",
            name=op.f("ck_entries_lifecycle"),
        ),
        sa.CheckConstraint(
            "checked_in_at IS NULL OR checked_in_at >= created_at",
            name=op.f("ck_entries_checked_after_created"),
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name=op.f("ck_entries_updated_after_created"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_entries_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_impulse_purchase_entries"),
    )
    op.create_index(
        "ix_entries_user_status_created",
        "impulse_purchase_entries",
        ["user_id", "status", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_entries_user_status_checked",
        "impulse_purchase_entries",
        ["user_id", "status", sa.literal_column("checked_in_at DESC")],
        unique=False,
    )

    op.create_table(
        "opportunity_cost_examples",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("unit_name", sa.String(length=80), nullable=False),
        sa.Column("dollar_value_cents", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(btrim(label)) > 0",
            name=op.f("ck_opportunity_cost_examples_label_not_blank"),
        ),
        sa.CheckConstraint(
            "length(btrim(unit_name)) > 0",
            name=op.f("ck_opportunity_cost_examples_unit_name_not_blank"),
        ),
        sa.CheckConstraint(
            "dollar_value_cents BETWEEN 1 AND 999999999999",
            name=op.f("ck_opportunity_cost_examples_dollar_value"),
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name=op.f("ck_opportunity_cost_examples_updated_after_created"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_opportunity_cost_examples_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_opportunity_cost_examples"),
    )
    op.create_index(
        "ix_opportunity_cost_examples_user_created",
        "opportunity_cost_examples",
        ["user_id", "created_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop all initial objects in reverse dependency order."""
    op.drop_index(
        "ix_opportunity_cost_examples_user_created",
        table_name="opportunity_cost_examples",
    )
    op.drop_table("opportunity_cost_examples")

    op.drop_index(
        "ix_entries_user_status_checked",
        table_name="impulse_purchase_entries",
    )
    op.drop_index(
        "ix_entries_user_status_created",
        table_name="impulse_purchase_entries",
    )
    op.drop_table("impulse_purchase_entries")

    op.drop_index("uq_sessions_token_hash", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_table("sessions")

    op.drop_index("uq_users_email", table_name="users")
    op.drop_table("users")
