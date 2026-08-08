"""Tests for production operations examples and their non-deploying validator."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from app.core.config import AppEnvironment, LogFormat, Settings

ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = ROOT / "operations" / "production.env.example"
VALIDATOR_PATH = ROOT / "scripts" / "check_operations.py"


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
