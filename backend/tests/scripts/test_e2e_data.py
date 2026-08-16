"""Safety and PostgreSQL behavior for isolated browser-test data."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.scripts.e2e_data import (
    E2EDataConfig,
    E2EDataSafetyError,
    build_manifest,
    load_config,
)

RUN_ID = "run-20260808-a1b2"
SETUP_AT = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)


def _config(tmp_path: Path, **changes: object) -> E2EDataConfig:
    values: dict[str, object] = {
        "database_url": ("postgresql+psycopg://e2e:secret@localhost:5432/penny_saved_e2e_test"),
        "run_id": RUN_ID,
        "email_domain": "browser.invalid",
        "password": "Ephemeral!Browser123",
        "setup_at": SETUP_AT,
        "manifest_path": tmp_path / "manifest.json",
    }
    values.update(changes)
    return E2EDataConfig(**values)  # type: ignore[arg-type]


def _environment(tmp_path: Path, **changes: str) -> dict[str, str]:
    values = {
        "APP_ENV": "test",
        "E2E_DATABASE_URL": ("postgresql+psycopg://e2e:secret@localhost:5432/penny_saved_e2e_test"),
        "E2E_RUN_ID": RUN_ID,
        "E2E_EMAIL_DOMAIN": "browser.invalid",
        "E2E_PASSWORD": "Ephemeral!Browser123",
        "E2E_SETUP_AT": SETUP_AT.isoformat(),
        "E2E_MANIFEST_PATH": str(tmp_path / "manifest.json"),
    }
    values.update(changes)
    return values


def test_load_config_requires_explicit_isolated_inputs(tmp_path: Path) -> None:
    config = load_config(_environment(tmp_path))

    assert config.run_id == RUN_ID
    assert config.setup_at == SETUP_AT


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"APP_ENV": "development"}, "APP_ENV"),
        ({"E2E_RUN_ID": "short"}, "E2E_RUN_ID"),
        ({"E2E_EMAIL_DOMAIN": "stopimpulsebuying.online"}, "production domain"),
        ({"E2E_DATABASE_URL": "postgresql+psycopg://x:y@db:5432/app_e2e_test"}, "loopback"),
        (
            {"E2E_DATABASE_URL": "postgresql+psycopg://x:y@localhost:5432/app_test"},
            "_e2e_test",
        ),
        ({"E2E_MANIFEST_PATH": "relative.json"}, "absolute"),
    ],
)
def test_load_config_rejects_unsafe_values(
    tmp_path: Path, changes: dict[str, str], message: str
) -> None:
    with pytest.raises(E2EDataSafetyError, match=message):
        load_config(_environment(tmp_path, **changes))


@pytest.mark.parametrize("ordinary_name", ["DATABASE_URL", "TEST_DATABASE_URL"])
def test_e2e_database_must_differ_from_ordinary_databases(
    tmp_path: Path, ordinary_name: str
) -> None:
    environment = _environment(tmp_path)
    environment[ordinary_name] = environment["E2E_DATABASE_URL"]

    with pytest.raises(E2EDataSafetyError, match=ordinary_name):
        load_config(environment)


def test_ci_database_host_requires_an_exact_explicit_approval(tmp_path: Path) -> None:
    environment = _environment(
        tmp_path,
        CI="true",
        E2E_DATABASE_URL="postgresql+psycopg://x:y@postgres:5432/app_e2e_test",
    )
    with pytest.raises(E2EDataSafetyError, match="E2E_CI_DATABASE_HOST"):
        load_config(environment)

    environment["E2E_CI_DATABASE_HOST"] = "postgres"
    assert load_config(environment).database_url == environment["E2E_DATABASE_URL"]


def test_manifest_is_deterministic_and_contains_no_password(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first = build_manifest(config)
    second = build_manifest(config)
    serialized = json.dumps(asdict(first))

    assert first == second
    assert RUN_ID in first.journey_user.email
    assert RUN_ID in first.eligible_item_name
    assert config.password not in serialized
    assert "database" not in serialized.lower()
