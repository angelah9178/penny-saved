"""Guarded entry point for deterministic development demo data."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, create_engine, or_, select
from sqlalchemy.engine import URL, make_url

from app.core.config import AppEnvironment, Settings, get_settings
from app.core.security import hash_password, verify_password
from app.core.time import Clock, SystemClock, normalize_utc
from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from app.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_CONFIG_PATH = BACKEND_ROOT / "alembic.ini"
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000007")
DEMO_USER_EMAIL = "demo@penny-saved.local"
DEMO_USER_PASSWORD = "PennySavedDemo!2026"


@dataclass(frozen=True, slots=True)
class DemoEntry:
    """One deterministic entry scenario relative to the seed clock."""

    id: UUID
    item_name: str
    price_cents: int
    reason_wanted: str
    status: EntryStatus
    created_ago: timedelta
    checked_in_ago: timedelta | None = None
    comment: str | None = None


DEMO_ENTRIES = (
    DemoEntry(
        id=UUID("10000000-0000-4000-8000-000000000001"),
        item_name="Ceramic travel mug",
        price_cents=2_400,
        reason_wanted="It looked useful for tomorrow's commute.",
        status=EntryStatus.WAITING,
        created_ago=timedelta(hours=6),
    ),
    DemoEntry(
        id=UUID("10000000-0000-4000-8000-000000000002"),
        item_name="Wireless headphones",
        price_cents=12_900,
        reason_wanted="A sale made an optional upgrade feel urgent.",
        status=EntryStatus.WAITING,
        created_ago=timedelta(hours=36),
    ),
    DemoEntry(
        id=UUID("10000000-0000-4000-8000-000000000003"),
        item_name="Running shoes",
        price_cents=9_500,
        reason_wanted="The color was new even though another pair still works.",
        status=EntryStatus.WAITING,
        created_ago=timedelta(hours=48),
    ),
    DemoEntry(
        id=UUID("10000000-0000-4000-8000-000000000004"),
        item_name="Drawing tablet",
        price_cents=27_500,
        reason_wanted="Starting a new hobby sounded exciting.",
        status=EntryStatus.WAITING,
        created_ago=timedelta(days=10),
    ),
    DemoEntry(
        id=UUID("10000000-0000-4000-8000-000000000005"),
        item_name="Desk lamp",
        price_cents=4_800,
        reason_wanted="The workspace could be brighter.",
        status=EntryStatus.SAVED,
        created_ago=timedelta(days=5),
        checked_in_ago=timedelta(days=3),
        comment="Moved the existing lamp and no longer needed a new one.",
    ),
    DemoEntry(
        id=UUID("10000000-0000-4000-8000-000000000006"),
        item_name="Lightweight jacket",
        price_cents=8_900,
        reason_wanted="It would have added another similar layer.",
        status=EntryStatus.SAVED,
        created_ago=timedelta(days=24),
        checked_in_ago=timedelta(days=21),
    ),
    DemoEntry(
        id=UUID("10000000-0000-4000-8000-000000000007"),
        item_name="Online design course",
        price_cents=19_900,
        reason_wanted="The enrollment countdown created pressure.",
        status=EntryStatus.SAVED,
        created_ago=timedelta(days=125),
        checked_in_ago=timedelta(days=120),
        comment="Finished a course already owned before buying another.",
    ),
    DemoEntry(
        id=UUID("10000000-0000-4000-8000-000000000008"),
        item_name="Espresso machine",
        price_cents=64_900,
        reason_wanted="Making café drinks at home sounded convenient.",
        status=EntryStatus.SAVED,
        created_ago=timedelta(days=505),
        checked_in_ago=timedelta(days=500),
    ),
    DemoEntry(
        id=UUID("10000000-0000-4000-8000-000000000009"),
        item_name="Concert ticket",
        price_cents=15_500,
        reason_wanted="Friends were attending and tickets were limited.",
        status=EntryStatus.PURCHASED,
        created_ago=timedelta(days=4),
        checked_in_ago=timedelta(days=2),
        comment="Waited, reviewed the budget, and chose to attend.",
    ),
)


class SeedSafetyError(RuntimeError):
    """Raised when demo seeding cannot prove its target is safe."""


@dataclass(frozen=True, slots=True)
class SeedResult:
    """Summary of one completed seed transaction."""

    seeded_at: datetime
    users: int = 0
    entries: int = 0
    opportunity_cost_examples: int = 0


EngineFactory = Callable[[str], Engine]
HeadVerifier = Callable[[Connection], None]
SeedOperation = Callable[[Connection, Clock], SeedResult]


def validate_seed_target(settings: Settings) -> URL:
    """Require an explicitly safe local development or test database."""
    if settings.app_env == AppEnvironment.PRODUCTION:
        raise SeedSafetyError("Refusing demo seed: APP_ENV=production is never allowed.")

    database_url = make_url(settings.database_url)
    if database_url.host not in LOOPBACK_HOSTS:
        raise SeedSafetyError(
            "Refusing demo seed: DATABASE_URL must use a loopback PostgreSQL host."
        )

    if settings.app_env == AppEnvironment.TEST and not database_url.database.endswith("_test"):
        raise SeedSafetyError("Refusing demo seed: test database name must end with '_test'.")

    return database_url


def compare_migration_heads(
    current_heads: set[str],
    expected_heads: set[str],
) -> None:
    """Require the database and checked-out Alembic history to have equal heads."""
    if current_heads != expected_heads:
        current = ", ".join(sorted(current_heads)) or "base"
        expected = ", ".join(sorted(expected_heads)) or "base"
        raise SeedSafetyError(
            "Refusing demo seed: database is not at the current Alembic head "
            f"(database: {current}; code: {expected}). Run 'make db-upgrade'."
        )


def require_migration_head(
    connection: Connection,
    *,
    config_path: Path = ALEMBIC_CONFIG_PATH,
) -> None:
    """Compare applied database heads with the heads declared by the code."""
    migration_context = MigrationContext.configure(connection)
    current_heads = set(migration_context.get_current_heads())
    script = ScriptDirectory.from_config(Config(config_path))
    compare_migration_heads(current_heads, set(script.get_heads()))


def seed_demo(
    connection: Connection,
    clock: Clock,
) -> SeedResult:
    """Reconcile the persistent demo user and return seed counts."""
    seeded_at = normalize_utc(clock.now())
    reconcile_demo_user(connection, seeded_at=seeded_at)
    reconcile_demo_entries(connection, seeded_at=seeded_at)
    return SeedResult(seeded_at=seeded_at, users=1, entries=len(DEMO_ENTRIES))


def reconcile_demo_user(connection: Connection, *, seeded_at: datetime) -> None:
    """Create or safely reconcile the one known demo account."""
    users = User.__table__
    matching_rows = (
        connection.execute(
            select(users.c.id, users.c.email, users.c.password_hash).where(
                or_(users.c.id == DEMO_USER_ID, users.c.email == DEMO_USER_EMAIL)
            )
        )
        .mappings()
        .all()
    )

    if not matching_rows:
        connection.execute(
            users.insert().values(
                id=DEMO_USER_ID,
                email=DEMO_USER_EMAIL,
                password_hash=hash_password(DEMO_USER_PASSWORD),
                created_at=seeded_at,
                updated_at=seeded_at,
            )
        )
        return

    if len(matching_rows) != 1:
        raise SeedSafetyError(
            "Refusing demo seed: the demo UUID and email belong to different users."
        )

    demo_user = matching_rows[0]
    if demo_user["id"] != DEMO_USER_ID or demo_user["email"] != DEMO_USER_EMAIL:
        raise SeedSafetyError(
            "Refusing demo seed: the demo UUID or email belongs to an unrelated user."
        )

    if not verify_password(DEMO_USER_PASSWORD, demo_user["password_hash"]):
        connection.execute(
            users.update()
            .where(users.c.id == DEMO_USER_ID)
            .values(
                password_hash=hash_password(DEMO_USER_PASSWORD),
                updated_at=seeded_at,
            )
        )


def reconcile_demo_entries(connection: Connection, *, seeded_at: datetime) -> None:
    """Create or restore the known demo-owned entry scenarios."""
    entries = ImpulsePurchaseEntry.__table__
    demo_ids = tuple(entry.id for entry in DEMO_ENTRIES)
    existing_owners = dict(
        connection.execute(
            select(entries.c.id, entries.c.user_id).where(entries.c.id.in_(demo_ids))
        ).all()
    )
    conflicting_ids = sorted(
        str(entry_id) for entry_id, owner_id in existing_owners.items() if owner_id != DEMO_USER_ID
    )
    if conflicting_ids:
        raise SeedSafetyError(
            "Refusing demo seed: known demo entry IDs belong to another user: "
            + ", ".join(conflicting_ids)
        )

    for demo_entry in DEMO_ENTRIES:
        created_at = seeded_at - demo_entry.created_ago
        checked_in_at = (
            None if demo_entry.checked_in_ago is None else seeded_at - demo_entry.checked_in_ago
        )
        values = {
            "user_id": DEMO_USER_ID,
            "item_name": demo_entry.item_name,
            "price_cents": demo_entry.price_cents,
            "reason_wanted": demo_entry.reason_wanted,
            "status": demo_entry.status,
            "comment": demo_entry.comment,
            "created_at": created_at,
            "checked_in_at": checked_in_at,
            "updated_at": seeded_at,
        }
        if demo_entry.id in existing_owners:
            connection.execute(
                entries.update().where(entries.c.id == demo_entry.id).values(**values)
            )
        else:
            connection.execute(entries.insert().values(id=demo_entry.id, **values))


def run_seed(
    settings: Settings,
    *,
    clock: Clock | None = None,
    engine_factory: EngineFactory = create_engine,
    head_verifier: HeadVerifier = require_migration_head,
    seed_operation: SeedOperation = seed_demo,
) -> SeedResult:
    """Validate, transact, and return one all-or-nothing demo seed result."""
    validate_seed_target(settings)
    resolved_clock = clock or SystemClock()
    engine = engine_factory(settings.database_url)
    try:
        with engine.begin() as connection:
            head_verifier(connection)
            return seed_operation(connection, resolved_clock)
    finally:
        engine.dispose()


def main() -> int:
    """Run guarded demo seeding from the command line."""
    try:
        result = run_seed(get_settings())
    except SeedSafetyError as error:
        print(error, file=sys.stderr)
        return 1

    print(
        f"Demo seed complete for {DEMO_USER_EMAIL} "
        f"(users={result.users}, entries={result.entries}, "
        f"opportunity_cost_examples={result.opportunity_cost_examples}, "
        f"seeded_at={result.seeded_at.isoformat()})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
