"""Guarded entry point for deterministic development demo data."""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
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
from app.models.user import User

BACKEND_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_CONFIG_PATH = BACKEND_ROOT / "alembic.ini"
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000007")
DEMO_USER_EMAIL = "demo@penny-saved.local"
DEMO_USER_PASSWORD = "PennySavedDemo!2026"


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
    return SeedResult(seeded_at=seeded_at, users=1)


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
