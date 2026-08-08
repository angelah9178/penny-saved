"""Guarded, deterministic data setup and cleanup for browser smoke tests."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID, uuid5

from sqlalchemy import Connection, Engine, create_engine, or_, select
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

from app.core.security import hash_password, verify_password
from app.core.time import normalize_utc
from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from app.models.opportunity_cost_example import OpportunityCostExample
from app.models.user import User
from app.scripts.seed_demo import SeedSafetyError, require_migration_head

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{7,63}$")
EMAIL_DOMAIN_PATTERN = re.compile(
    r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)
E2E_NAMESPACE = UUID("8238be29-76ef-4c31-9cb3-19f7c56db803")
MANIFEST_VERSION = 1


class E2EDataSafetyError(RuntimeError):
    """Raised when browser data operations cannot prove their scope is safe."""


@dataclass(frozen=True, slots=True)
class E2EDataConfig:
    """Validated inputs for one isolated browser-test data run."""

    database_url: str
    run_id: str
    email_domain: str
    password: str
    setup_at: datetime
    manifest_path: Path


@dataclass(frozen=True, slots=True)
class E2EUserManifest:
    id: str
    email: str


@dataclass(frozen=True, slots=True)
class E2EDataManifest:
    """Secret-free contract passed from data setup to browser orchestration."""

    version: int
    run_id: str
    setup_at: str
    signup_user: E2EUserManifest
    journey_user: E2EUserManifest
    eligible_entry_id: str
    eligible_item_name: str
    initial_saved_total_cents: int
    expected_saved_total_cents: int
    whole_equivalent_label: str
    fractional_equivalent_label: str


EngineFactory = Callable[[str], Engine]
HeadVerifier = Callable[[Connection], None]


def load_config(environment: Mapping[str, str] = os.environ) -> E2EDataConfig:
    """Load required inputs without falling back to ordinary app configuration."""
    if environment.get("APP_ENV", "").lower() != "test":
        raise E2EDataSafetyError("Refusing E2E data operation: APP_ENV must be 'test'.")

    required = (
        "E2E_DATABASE_URL",
        "E2E_RUN_ID",
        "E2E_EMAIL_DOMAIN",
        "E2E_PASSWORD",
        "E2E_SETUP_AT",
        "E2E_MANIFEST_PATH",
    )
    missing = [name for name in required if not environment.get(name)]
    if missing:
        raise E2EDataSafetyError("Refusing E2E data operation: missing " + ", ".join(missing) + ".")

    database_url = environment["E2E_DATABASE_URL"]
    for ordinary_name in ("DATABASE_URL", "TEST_DATABASE_URL"):
        ordinary_url = environment.get(ordinary_name)
        if ordinary_url:
            try:
                same_url = make_url(ordinary_url) == make_url(database_url)
            except ArgumentError as error:
                raise E2EDataSafetyError("Database URLs must be valid SQLAlchemy URLs.") from error
            if same_url:
                raise E2EDataSafetyError(
                    f"Refusing E2E data operation: E2E_DATABASE_URL matches {ordinary_name}."
                )

    try:
        setup_at = normalize_utc(datetime.fromisoformat(environment["E2E_SETUP_AT"]))
    except ValueError as error:
        raise E2EDataSafetyError("E2E_SETUP_AT must be an ISO-8601 UTC timestamp.") from error

    config = E2EDataConfig(
        database_url=database_url,
        run_id=environment["E2E_RUN_ID"],
        email_domain=environment["E2E_EMAIL_DOMAIN"].lower(),
        password=environment["E2E_PASSWORD"],
        setup_at=setup_at,
        manifest_path=Path(environment["E2E_MANIFEST_PATH"]),
    )
    validate_config(config, environment=environment)
    return config


def validate_config(config: E2EDataConfig, *, environment: Mapping[str, str]) -> URL:
    """Refuse ambiguous identifiers, credentials, paths, and database targets."""
    if not RUN_ID_PATTERN.fullmatch(config.run_id):
        raise E2EDataSafetyError("E2E_RUN_ID must be 8-64 lowercase letters, digits, or hyphens.")
    if not EMAIL_DOMAIN_PATTERN.fullmatch(config.email_domain):
        raise E2EDataSafetyError("E2E_EMAIL_DOMAIN must be a valid dedicated domain.")
    if config.email_domain in {"penny-saved.local", "stopimpulsebuying.us"}:
        raise E2EDataSafetyError("E2E_EMAIL_DOMAIN must not be a demo or production domain.")
    if not 8 <= len(config.password) <= 128:
        raise E2EDataSafetyError("E2E_PASSWORD must contain 8-128 characters.")
    if config.setup_at.utcoffset() != timedelta(0):
        raise E2EDataSafetyError("E2E_SETUP_AT must include the UTC offset.")
    if not config.manifest_path.is_absolute():
        raise E2EDataSafetyError("E2E_MANIFEST_PATH must be an absolute caller-owned path.")

    try:
        url = make_url(config.database_url)
    except ArgumentError as error:
        raise E2EDataSafetyError("E2E_DATABASE_URL must be a valid SQLAlchemy URL.") from error
    if url.drivername != "postgresql+psycopg" or not url.database:
        raise E2EDataSafetyError("E2E_DATABASE_URL must use postgresql+psycopg with a database.")
    if not url.database.endswith("_e2e_test"):
        raise E2EDataSafetyError("E2E database name must end with '_e2e_test'.")

    if environment.get("CI", "").lower() == "true":
        approved_host = environment.get("E2E_CI_DATABASE_HOST")
        if not approved_host or url.host != approved_host:
            raise E2EDataSafetyError(
                "CI requires E2E_CI_DATABASE_HOST to exactly match the database host."
            )
    elif url.host not in LOOPBACK_HOSTS:
        raise E2EDataSafetyError("Local E2E_DATABASE_URL must use a loopback host.")
    return url


def _identity(run_id: str, role: str, domain: str) -> tuple[UUID, str]:
    return uuid5(E2E_NAMESPACE, f"{run_id}:{role}"), f"e2e-{run_id}-{role}@{domain}"


def build_manifest(config: E2EDataConfig) -> E2EDataManifest:
    """Build stable identifiers and browser-visible expectations for one run."""
    signup_id, signup_email = _identity(config.run_id, "signup", config.email_domain)
    journey_id, journey_email = _identity(config.run_id, "journey", config.email_domain)
    eligible_id = uuid5(E2E_NAMESPACE, f"{config.run_id}:eligible-entry")
    return E2EDataManifest(
        version=MANIFEST_VERSION,
        run_id=config.run_id,
        setup_at=config.setup_at.isoformat(),
        signup_user=E2EUserManifest(id=str(signup_id), email=signup_email),
        journey_user=E2EUserManifest(id=str(journey_id), email=journey_email),
        eligible_entry_id=str(eligible_id),
        eligible_item_name=f"Eligible headphones [{config.run_id}]",
        initial_saved_total_cents=5_000,
        expected_saved_total_cents=12_500,
        whole_equivalent_label=f"Transit rides [{config.run_id}]",
        fractional_equivalent_label=f"Lunches [{config.run_id}]",
    )


def _assert_or_create_user(
    connection: Connection,
    *,
    user: E2EUserManifest,
    password: str,
    now: datetime,
) -> None:
    table = User.__table__
    rows = (
        connection.execute(
            select(table.c.id, table.c.email, table.c.password_hash).where(
                or_(table.c.id == UUID(user.id), table.c.email == user.email)
            )
        )
        .mappings()
        .all()
    )
    if not rows:
        connection.execute(
            table.insert().values(
                id=UUID(user.id),
                email=user.email,
                password_hash=hash_password(password),
                created_at=now,
                updated_at=now,
            )
        )
        return
    if len(rows) != 1 or rows[0]["id"] != UUID(user.id) or rows[0]["email"] != user.email:
        raise E2EDataSafetyError("Run-scoped user identity conflicts with an unrelated row.")
    if not verify_password(password, rows[0]["password_hash"]):
        raise E2EDataSafetyError("Existing run-scoped user has a conflicting specification.")


def _insert_or_verify(
    connection: Connection,
    *,
    table: object,
    record_id: UUID,
    values: dict[str, object],
) -> None:
    row = connection.execute(select(table).where(table.c.id == record_id)).mappings().one_or_none()
    if row is None:
        connection.execute(table.insert().values(id=record_id, **values))
        return
    if any(row[key] != value for key, value in values.items()):
        raise E2EDataSafetyError("Existing run-owned data has a conflicting specification.")


def setup_data(connection: Connection, config: E2EDataConfig) -> E2EDataManifest:
    """Create an exact, deterministic starting point in one transaction."""
    manifest = build_manifest(config)
    _assert_or_create_user(
        connection,
        user=manifest.journey_user,
        password=config.password,
        now=config.setup_at,
    )
    journey_id = UUID(manifest.journey_user.id)

    _insert_or_verify(
        connection,
        table=ImpulsePurchaseEntry.__table__,
        record_id=UUID(manifest.eligible_entry_id),
        values={
            "user_id": journey_id,
            "item_name": manifest.eligible_item_name,
            "price_cents": 7_500,
            "reason_wanted": f"Browser journey [{config.run_id}]",
            "status": EntryStatus.WAITING,
            "comment": None,
            "created_at": config.setup_at - timedelta(hours=49),
            "checked_in_at": None,
            "updated_at": config.setup_at - timedelta(hours=49),
        },
    )
    saved_id = uuid5(E2E_NAMESPACE, f"{config.run_id}:saved-entry")
    _insert_or_verify(
        connection,
        table=ImpulsePurchaseEntry.__table__,
        record_id=saved_id,
        values={
            "user_id": journey_id,
            "item_name": f"Saved desk lamp [{config.run_id}]",
            "price_cents": manifest.initial_saved_total_cents,
            "reason_wanted": f"Statistics baseline [{config.run_id}]",
            "status": EntryStatus.SAVED,
            "comment": "Deterministic browser-test history.",
            "created_at": config.setup_at - timedelta(days=5),
            "checked_in_at": config.setup_at - timedelta(days=3),
            "updated_at": config.setup_at - timedelta(days=3),
        },
    )
    examples = (
        ("whole", manifest.whole_equivalent_label, "transit ride", 2_500),
        ("fractional", manifest.fractional_equivalent_label, "lunch", 4_000),
    )
    for key, label, unit_name, cents in examples:
        _insert_or_verify(
            connection,
            table=OpportunityCostExample.__table__,
            record_id=uuid5(E2E_NAMESPACE, f"{config.run_id}:{key}-example"),
            values={
                "user_id": journey_id,
                "label": label,
                "unit_name": unit_name,
                "dollar_value_cents": cents,
                "created_at": config.setup_at,
                "updated_at": config.setup_at,
            },
        )
    return manifest


def cleanup_data(connection: Connection, manifest: E2EDataManifest) -> int:
    """Delete only the two exact users identified by a validated manifest."""
    expected = (manifest.signup_user, manifest.journey_user)
    deleted = 0
    for user in expected:
        result = connection.execute(
            User.__table__.delete().where(
                User.__table__.c.id == UUID(user.id), User.__table__.c.email == user.email
            )
        )
        deleted += result.rowcount
    return deleted


def _write_manifest(path: Path, manifest: E2EDataManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
        json.dump(asdict(manifest), handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary_path = Path(handle.name)
    temporary_path.replace(path)


def _read_manifest(path: Path, config: E2EDataConfig) -> E2EDataManifest:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        manifest = E2EDataManifest(
            version=raw["version"],
            run_id=raw["run_id"],
            setup_at=raw["setup_at"],
            signup_user=E2EUserManifest(**raw["signup_user"]),
            journey_user=E2EUserManifest(**raw["journey_user"]),
            eligible_entry_id=raw["eligible_entry_id"],
            eligible_item_name=raw["eligible_item_name"],
            initial_saved_total_cents=raw["initial_saved_total_cents"],
            expected_saved_total_cents=raw["expected_saved_total_cents"],
            whole_equivalent_label=raw["whole_equivalent_label"],
            fractional_equivalent_label=raw["fractional_equivalent_label"],
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise E2EDataSafetyError("Manifest is missing or invalid; refusing cleanup.") from error
    if manifest != build_manifest(config) or manifest.version != MANIFEST_VERSION:
        raise E2EDataSafetyError("Manifest does not exactly match this E2E run specification.")
    return manifest


def run_setup(
    config: E2EDataConfig,
    *,
    engine_factory: EngineFactory = create_engine,
    head_verifier: HeadVerifier = require_migration_head,
) -> E2EDataManifest:
    manifest = build_manifest(config)
    # Preflight and atomically record the exact cleanup scope before database mutation.
    _write_manifest(config.manifest_path, manifest)
    engine = engine_factory(config.database_url)
    try:
        with engine.begin() as connection:
            head_verifier(connection)
            if setup_data(connection, config) != manifest:
                raise E2EDataSafetyError("Setup result did not match its cleanup manifest.")
        return manifest
    except SeedSafetyError as error:
        raise E2EDataSafetyError(str(error)) from error
    finally:
        engine.dispose()


def run_cleanup(
    config: E2EDataConfig,
    *,
    engine_factory: EngineFactory = create_engine,
    head_verifier: HeadVerifier = require_migration_head,
) -> int:
    manifest = _read_manifest(config.manifest_path, config)
    engine = engine_factory(config.database_url)
    try:
        with engine.begin() as connection:
            head_verifier(connection)
            return cleanup_data(connection, manifest)
    except SeedSafetyError as error:
        raise E2EDataSafetyError(str(error)) from error
    finally:
        engine.dispose()


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("setup", "cleanup"))
    args = parser.parse_args(arguments)
    try:
        config = load_config()
        if args.operation == "setup":
            manifest = run_setup(config)
            print(f"E2E data setup complete for run {manifest.run_id}.")
        else:
            deleted = run_cleanup(config)
            print(f"E2E data cleanup complete; removed {deleted} run-owned users.")
    except E2EDataSafetyError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
