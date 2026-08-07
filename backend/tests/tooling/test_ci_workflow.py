"""Static contract tests for the GitHub Actions quality workflow."""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "quality.yml"


def _workflow() -> dict[str, Any]:
    loaded = yaml.load(WORKFLOW_PATH.read_text(), Loader=yaml.BaseLoader)
    assert isinstance(loaded, dict)
    return loaded


def _steps(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {step["name"]: step for step in job["steps"]}


def test_quality_workflow_has_safe_triggers_permissions_and_concurrency() -> None:
    workflow = _workflow()

    assert workflow["on"] == {
        "pull_request": "",
        "push": {"branches": ["main"]},
    }
    assert workflow["permissions"] == {"contents": "read"}
    assert workflow["concurrency"]["cancel-in-progress"] == "true"
    assert "github.event.pull_request.number" in workflow["concurrency"]["group"]
    assert "github.ref" in workflow["concurrency"]["group"]


def test_frontend_job_uses_locked_dependencies_and_all_required_checks() -> None:
    frontend = _workflow()["jobs"]["frontend"]
    steps = _steps(frontend)

    assert frontend["name"] == "frontend"
    assert frontend["timeout-minutes"] == "15"
    assert steps["Check out repository"]["uses"] == "actions/checkout@v6"
    assert steps["Set up Node.js"]["uses"] == "actions/setup-node@v6"
    assert steps["Set up Node.js"]["with"] == {
        "node-version-file": ".nvmrc",
        "cache": "npm",
        "cache-dependency-path": "frontend/package-lock.json",
    }
    assert steps["Install locked frontend dependencies"]["run"] == "npm ci"

    expected_commands = {
        "npm ci",
        "npm run format:check",
        "npm run lint",
        "npm run typecheck",
        "npm test",
        "npm run build",
    }
    assert {step["run"] for step in frontend["steps"] if "run" in step} == expected_commands
    assert all(
        step.get("working-directory") == "frontend" for step in frontend["steps"] if "run" in step
    )


def test_backend_job_uses_postgresql_pinned_dependencies_and_required_checks() -> None:
    backend = _workflow()["jobs"]["backend"]
    steps = _steps(backend)
    postgres = backend["services"]["postgres"]

    assert backend["name"] == "backend"
    assert backend["timeout-minutes"] == "15"
    assert postgres["image"] == "postgres:16"
    assert postgres["env"]["POSTGRES_DB"].endswith("_test")
    assert "pg_isready" in postgres["options"]
    assert "--health-retries" in postgres["options"]
    assert backend["env"]["APP_ENV"] == "test"
    assert backend["env"]["TEST_DATABASE_URL"].endswith("/penny_saved_test")
    assert backend["env"]["DATABASE_URL"] != backend["env"]["TEST_DATABASE_URL"]

    assert steps["Check out repository"]["uses"] == "actions/checkout@v6"
    assert steps["Set up Python"]["uses"] == "actions/setup-python@v6"
    assert steps["Set up Python"]["with"]["python-version-file"] == ".python-version"
    assert steps["Set up Python"]["with"]["cache"] == "pip"
    assert "backend/requirements.txt" in steps["Set up Python"]["with"]["cache-dependency-path"]
    assert "backend/requirements-dev.txt" in steps["Set up Python"]["with"]["cache-dependency-path"]

    expected_commands = {
        "python -m pip install -r requirements-dev.txt",
        "python -m ruff format --check .",
        "python -m ruff check .",
        "python -m pytest",
    }
    assert {step["run"] for step in backend["steps"] if "run" in step} == expected_commands
    assert all(
        step.get("working-directory") == "backend" for step in backend["steps"] if "run" in step
    )


def test_migrations_job_cycles_postgresql_schema_and_checks_drift() -> None:
    migrations = _workflow()["jobs"]["migrations"]
    steps = _steps(migrations)
    postgres = migrations["services"]["postgres"]

    assert migrations["name"] == "migrations"
    assert migrations["timeout-minutes"] == "15"
    assert postgres["image"] == "postgres:16"
    assert postgres["env"]["POSTGRES_DB"] == "penny_saved_test"
    assert "pg_isready" in postgres["options"]
    assert migrations["env"]["APP_ENV"] == "test"
    assert migrations["env"]["TEST_DATABASE_URL"].endswith("/penny_saved_test")
    assert migrations["env"]["DATABASE_URL"] != migrations["env"]["TEST_DATABASE_URL"]

    assert steps["Check out repository"]["uses"] == "actions/checkout@v6"
    assert steps["Set up Python"]["uses"] == "actions/setup-python@v6"
    assert steps["Set up Python"]["with"]["python-version-file"] == ".python-version"
    assert steps["Set up Python"]["with"]["cache"] == "pip"
    assert (
        steps["Upgrade empty database to migration head"]["env"]["DATABASE_URL"]
        == "${{ env.TEST_DATABASE_URL }}"
    )
    assert (
        steps["Downgrade complete migration history to base"]["env"]["DATABASE_URL"]
        == "${{ env.TEST_DATABASE_URL }}"
    )
    assert (
        steps["Re-upgrade database to migration head"]["env"]["DATABASE_URL"]
        == "${{ env.TEST_DATABASE_URL }}"
    )
    assert (
        steps["Check model and migration drift"]["env"]["DATABASE_URL"]
        == "${{ env.TEST_DATABASE_URL }}"
    )

    migration_commands = [
        "python -m alembic upgrade head",
        "python -m alembic downgrade base",
        "python -m alembic upgrade head",
        "python -m alembic check",
    ]
    actual_commands = [
        step["run"]
        for step in migrations["steps"]
        if step["name"]
        not in {
            "Check out repository",
            "Set up Python",
            "Install pinned backend dependencies",
            "Test PostgreSQL schema and migrations",
        }
    ]
    assert actual_commands == migration_commands
    focused_tests = steps["Test PostgreSQL schema and migrations"]["run"]
    assert "tests/integration/test_database_schema.py" in focused_tests
    assert "tests/integration/test_migrations.py" in focused_tests


def test_workflow_needs_no_secrets_and_never_uses_sqlite() -> None:
    workflow_text = WORKFLOW_PATH.read_text().lower()

    assert "secrets." not in workflow_text
    assert "sqlite" not in workflow_text


def test_security_job_uses_locked_inputs_read_only_tools_and_bounded_runtime() -> None:
    security = _workflow()["jobs"]["security"]
    steps = _steps(security)

    assert security["name"] == "security"
    assert security["timeout-minutes"] == "15"
    assert steps["Check out repository"]["uses"] == "actions/checkout@v6"
    assert steps["Set up Node.js"]["uses"] == "actions/setup-node@v6"
    assert steps["Set up Python"]["uses"] == "actions/setup-python@v6"
    assert steps["Install locked frontend dependencies"]["run"] == "npm ci"
    assert steps["Install pinned backend security tooling"]["run"] == (
        "python -m pip install -r requirements-dev.txt"
    )
    assert steps["Audit locked frontend dependencies"]["run"] == "node scripts/audit-frontend.mjs"
    assert steps["Audit pinned backend runtime dependencies"]["run"] == (
        "python -m pip_audit --requirement requirements.txt --progress-spinner off"
    )
    assert "--fix" not in WORKFLOW_PATH.read_text()
