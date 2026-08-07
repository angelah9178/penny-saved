"""Add shared rate-limit counters.

Revision ID: 0002_rate_limit_counters
Revises: 0001_initial_schema
Create Date: 2026-08-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_rate_limit_counters"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the shared fixed-window counter table."""
    op.create_table(
        "rate_limit_counters",
        sa.Column("bucket", sa.String(length=64), nullable=False),
        sa.Column("key_digest", sa.CHAR(length=64), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(btrim(bucket)) > 0",
            name=op.f("ck_rate_limit_counters_bucket_not_blank"),
        ),
        sa.CheckConstraint(
            "key_digest ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_rate_limit_counters_key_digest_format"),
        ),
        sa.CheckConstraint(
            "attempt_count > 0",
            name=op.f("ck_rate_limit_counters_attempt_count_positive"),
        ),
        sa.CheckConstraint(
            "expires_at > window_started_at",
            name=op.f("ck_rate_limit_counters_window_expiry"),
        ),
        sa.PrimaryKeyConstraint("bucket", "key_digest", name="pk_rate_limit_counters"),
    )
    op.create_index(
        "ix_rate_limit_counters_expires_at",
        "rate_limit_counters",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove shared rate-limit storage."""
    op.drop_index(
        "ix_rate_limit_counters_expires_at",
        table_name="rate_limit_counters",
    )
    op.drop_table("rate_limit_counters")
