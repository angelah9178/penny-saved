"""Tests for production operations examples and their non-deploying validator."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest
from app.core.config import AppEnvironment, LogFormat, Settings

ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = ROOT / "operations" / "production.env.example"
VALIDATOR_PATH = ROOT / "scripts" / "check_operations.py"
RELEASE_DECISIONS = ROOT / "development" / "release-decisions.md"
RELEASE_RUNBOOK = ROOT / "operations" / "RELEASE.md"


def _load_validator() -> object:
    spec = importlib.util.spec_from_file_location("check_operations", VALIDATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_production_environment_example_constructs_safe_typed_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for field_name in Settings.model_fields:
        monkeypatch.delenv(field_name.upper(), raising=False)

    settings = Settings(_env_file=ENV_EXAMPLE)

    assert settings.app_env is AppEnvironment.PRODUCTION
    assert settings.frontend_origin == "https://stopimpulsebuying.us"
    assert settings.session_cookie_secure is True
    assert settings.log_format is LogFormat.JSON
    assert settings.metrics_enabled is True
    assert settings.trusted_proxy_networks == ("127.0.0.1/32", "::1/128")
    assert "REPLACE_WITH" in settings.database_url
    assert "REPLACE_WITH" in settings.rate_limit_key_secret.get_secret_value()


def test_operations_examples_pass_repository_static_validation() -> None:
    validator = _load_validator()

    assert validator.validate() == []


def test_release_runbook_is_ordered_safe_and_non_deploying() -> None:
    text = RELEASE_RUNBOOK.read_text()

    headings = [f"## {number}." for number in range(1, 11)]
    positions = [text.index(heading) for heading in headings]
    assert positions == sorted(positions)
    assert text.index("### Capacity Stop Check") < text.index("## 3. Go or No-Go")
    assert text.count("PRODUCTION ACTION — REQUIRES SEPARATE AUTHORIZATION") >= 3
    assert "make deploy" not in text
    assert "Do not automatically run `alembic downgrade`" in text


def test_release_decisions_are_complete_current_and_secret_free() -> None:
    validator = _load_validator()
    decisions = validator.parse_release_decisions(RELEASE_DECISIONS.read_text())

    assert validator.validate_release_decisions(decisions, today=date(2026, 8, 12)) == []
    assert {item["status"] for item in decisions} == {
        "ready",
        "deferred",
        "blocked",
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("owner", "", "blank owner"),
        ("status", "unknown", "invalid status"),
        ("deadline", "2026-08-11", "expired deadline"),
        ("decision", "password=production-value", "secret-like material"),
    ],
)
def test_release_decision_validator_rejects_unsafe_or_incomplete_answers(
    field: str, value: str, message: str
) -> None:
    validator = _load_validator()
    decisions = validator.parse_release_decisions(RELEASE_DECISIONS.read_text())
    decisions[0][field] = value

    assert any(
        message in error
        for error in validator.validate_release_decisions(decisions, today=date(2026, 8, 12))
    )
