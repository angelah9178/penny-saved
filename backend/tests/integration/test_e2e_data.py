"""PostgreSQL behavior for isolated browser-test data."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from app.core.security import verify_password
from app.models.entry import EntryStatus, ImpulsePurchaseEntry
from app.models.opportunity_cost_example import OpportunityCostExample
from app.models.user import User
from app.scripts.e2e_data import (
    E2EDataConfig,
    E2EDataSafetyError,
    build_manifest,
    cleanup_data,
    run_cleanup,
    run_setup,
    setup_data,
    verify_auth_entry_data,
    verify_complete_journey_data,
)
from sqlalchemy import Connection, func, select
from sqlalchemy.engine import URL

RUN_ID = "run-20260808-a1b2"
SETUP_AT = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def _config(tmp_path: Path, **changes: object) -> E2EDataConfig:
    values: dict[str, object] = {
        "database_url": "postgresql+psycopg://unused/unused_e2e_test",
        "run_id": RUN_ID,
        "email_domain": "browser.invalid",
        "password": "Ephemeral!Browser123",
        "setup_at": SETUP_AT,
        "manifest_path": tmp_path / "manifest.json",
    }
    values.update(changes)
    return E2EDataConfig(**values)  # type: ignore[arg-type]


def test_setup_is_deterministic_eligible_and_produces_expected_totals(
    db_connection: Connection, tmp_path: Path
) -> None:
    config = _config(tmp_path)
    manifest = setup_data(db_connection, config)
    repeated = setup_data(db_connection, config)

    assert repeated == manifest
    password_hashes = db_connection.execute(select(User.password_hash)).scalars().all()
    assert len(password_hashes) == 1
    assert all(verify_password(config.password, password_hash) for password_hash in password_hashes)

    entries = (
        db_connection.execute(
            select(ImpulsePurchaseEntry.__table__).where(
                ImpulsePurchaseEntry.__table__.c.user_id == UUID(manifest.journey_user.id)
            )
        )
        .mappings()
        .all()
    )
    assert len(entries) == 2
    eligible = next(entry for entry in entries if entry["id"] == UUID(manifest.eligible_entry_id))
    assert eligible["status"] is EntryStatus.WAITING
    assert config.setup_at - eligible["created_at"] == timedelta(hours=49)
    assert (
        sum(entry["price_cents"] for entry in entries if entry["status"] is EntryStatus.SAVED)
        == 5_000
    )

    example_values = (
        db_connection.execute(
            select(OpportunityCostExample.dollar_value_cents).where(
                OpportunityCostExample.user_id == UUID(manifest.journey_user.id)
            )
        )
        .scalars()
        .all()
    )
    assert set(example_values) == {2_500, 4_000}
    assert manifest.expected_saved_total_cents / 2_500 == 5
    assert manifest.expected_saved_total_cents / 4_000 == 3.125


def test_setup_refuses_a_conflicting_existing_run(
    db_connection: Connection, tmp_path: Path
) -> None:
    setup_data(db_connection, _config(tmp_path))

    with pytest.raises(E2EDataSafetyError, match="conflicting specification"):
        setup_data(db_connection, _config(tmp_path, password="Different!Password456"))


def test_cleanup_is_exact_preserves_unrelated_rows_and_is_idempotent(
    db_connection: Connection, tmp_path: Path
) -> None:
    config = _config(tmp_path)
    manifest = setup_data(db_connection, config)
    unrelated_id = uuid4()
    db_connection.execute(
        User.__table__.insert().values(
            id=unrelated_id,
            email=f"unrelated@{config.email_domain}",
            password_hash="not-a-real-hash",
            created_at=SETUP_AT,
            updated_at=SETUP_AT,
        )
    )

    assert cleanup_data(db_connection, manifest) == 1
    assert cleanup_data(db_connection, manifest) == 0
    assert (
        db_connection.execute(
            select(func.count()).select_from(User).where(User.id == unrelated_id)
        ).scalar_one()
        == 1
    )
    assert (
        db_connection.execute(select(func.count()).select_from(ImpulsePurchaseEntry)).scalar_one()
        == 0
    )
    assert (
        db_connection.execute(select(func.count()).select_from(OpportunityCostExample)).scalar_one()
        == 0
    )


def test_auth_entry_verification_accepts_api_assigned_signup_id_and_cleanup(
    db_connection: Connection, tmp_path: Path
) -> None:
    config = _config(tmp_path)
    manifest = setup_data(db_connection, config)
    signup_id = uuid4()
    db_connection.execute(
        User.__table__.insert().values(
            id=signup_id,
            email=manifest.signup_user.email,
            password_hash="normal-hash-placeholder",
            created_at=SETUP_AT,
            updated_at=SETUP_AT,
        )
    )
    db_connection.execute(
        ImpulsePurchaseEntry.__table__.insert().values(
            id=uuid4(),
            user_id=signup_id,
            item_name=manifest.signup_entry_item_name,
            price_cents=manifest.signup_entry_price_cents,
            reason_wanted=manifest.signup_entry_reason,
            status=EntryStatus.WAITING,
            comment=None,
            created_at=SETUP_AT,
            checked_in_at=None,
            updated_at=SETUP_AT,
        )
    )

    verify_auth_entry_data(db_connection, manifest)
    assert cleanup_data(db_connection, manifest) == 2


def test_complete_journey_verification_accepts_saved_check_in_and_revoked_session(
    db_connection: Connection, tmp_path: Path
) -> None:
    manifest = setup_data(db_connection, _config(tmp_path))
    db_connection.execute(
        ImpulsePurchaseEntry.__table__.update()
        .where(ImpulsePurchaseEntry.id == UUID(manifest.eligible_entry_id))
        .values(
            status=EntryStatus.SAVED,
            comment=manifest.check_in_comment,
            checked_in_at=SETUP_AT,
            updated_at=SETUP_AT,
        )
    )

    verify_complete_journey_data(db_connection, manifest)


def test_guarded_run_writes_secret_free_manifest_and_cleans_committed_data(
    test_database_url: URL, tmp_path: Path
) -> None:
    config = _config(
        tmp_path,
        run_id="run-20260808-committed",
        database_url=test_database_url.render_as_string(hide_password=False),
    )
    try:
        manifest = run_setup(config)
        manifest_text = config.manifest_path.read_text(encoding="utf-8")

        assert json.loads(manifest_text)["run_id"] == config.run_id
        assert manifest.run_id == config.run_id
        assert config.password not in manifest_text
        assert config.database_url not in manifest_text
        assert run_cleanup(config) == 1
        assert run_cleanup(config) == 0
    finally:
        if config.manifest_path.exists():
            run_cleanup(config)


def test_cleanup_refuses_a_manifest_from_another_run(
    test_database_url: URL, tmp_path: Path
) -> None:
    config = _config(
        tmp_path,
        database_url=test_database_url.render_as_string(hide_password=False),
    )
    manifest = asdict(build_manifest(config))
    manifest["run_id"] = "run-20260808-someone-else"
    config.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(E2EDataSafetyError, match="does not exactly match"):
        run_cleanup(config)
