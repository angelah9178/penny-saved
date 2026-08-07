"""Contract tests for the root quality command interface."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAKEFILE = ROOT / "Makefile"


def _makefile_text() -> str:
    return MAKEFILE.read_text()


def test_makefile_exposes_focused_and_combined_quality_targets() -> None:
    makefile = _makefile_text()

    expected_targets = {
        "frontend-format",
        "backend-format",
        "format",
        "frontend-format-check",
        "backend-format-check",
        "format-check",
        "frontend-lint",
        "backend-lint",
        "lint",
        "frontend-typecheck",
        "typecheck",
        "frontend-test",
        "backend-test",
        "test",
        "frontend-build",
        "backend-build",
        "build",
        "check",
        "clean",
        "frontend-dev",
        "backend-dev",
        "dev",
        "seed-demo",
        "frontend-security-check",
        "backend-security-check",
        "security-check",
    }
    phony = makefile.split(".PHONY:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]

    for target in expected_targets:
        assert f"{target}:" in makefile
        assert target in phony


def test_check_runs_quality_stages_in_the_documented_order() -> None:
    makefile = _makefile_text()
    check_recipe = makefile.split("\ncheck: ##", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]

    stages = ["format-check", "lint", "typecheck", "test", "build"]
    positions = [check_recipe.index(f"$(MAKE) {stage}") for stage in stages]

    assert positions == sorted(positions)


def test_backend_tests_require_explicit_local_environment_configuration() -> None:
    makefile = _makefile_text()
    backend_test = makefile.split("backend-test:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]

    assert "check-backend-env" in backend_test
    assert "source .env" in backend_test
    assert "TEST_DATABASE_URL=" not in backend_test
    assert "sqlite" not in backend_test.lower()


def test_backend_build_uses_test_only_settings_without_starting_a_server() -> None:
    makefile = _makefile_text()
    backend_build = makefile.split("backend-build:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]

    assert "APP_ENV=test" in backend_build
    assert "create_app()" in backend_build
    assert "uvicorn" not in backend_build


def test_clean_delegates_to_the_guarded_cleanup_script() -> None:
    makefile = _makefile_text()
    clean_recipe = makefile.split("\nclean: ##", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]

    assert "generated" in clean_recipe
    assert "./scripts/clean-generated.sh" in clean_recipe
    assert "rm " not in clean_recipe


def test_dev_starts_dependencies_before_the_process_supervisor() -> None:
    makefile = _makefile_text()
    dev_recipe = makefile.split("\ndev:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]

    stages = ["$(MAKE) db-up", "$(MAKE) db-upgrade", "./scripts/run-dev.sh"]
    positions = [dev_recipe.index(stage) for stage in stages]

    assert positions == sorted(positions)
    assert "check-frontend" in dev_recipe
    assert "check-backend-env" in dev_recipe
    assert "check-docker" in dev_recipe
    assert "check-alembic" in dev_recipe


def test_focused_dev_targets_use_the_supported_servers() -> None:
    makefile = _makefile_text()
    frontend_dev = makefile.split("\nfrontend-dev:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    backend_dev = makefile.split("\nbackend-dev:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]

    assert "npm --prefix frontend run dev" in frontend_dev
    assert "app.main:create_app" in backend_dev
    assert "--factory" in backend_dev
    assert "--reload" in backend_dev


def test_seed_demo_uses_backend_configuration_without_starting_dependencies() -> None:
    makefile = _makefile_text()
    seed_demo = makefile.split("\nseed-demo:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]

    assert "check-alembic" in seed_demo
    assert "cd backend" in seed_demo
    assert "$(BACKEND_PYTHON) -m app.scripts.seed_demo" in seed_demo
    assert "$(MAKE) db-up" not in seed_demo
    assert "$(MAKE) db-upgrade" not in seed_demo
    assert "pip install" not in seed_demo
    assert "npm " not in seed_demo


def test_security_check_uses_locked_frontend_and_pinned_backend_inputs() -> None:
    makefile = _makefile_text()
    frontend = makefile.split("frontend-security-check:", maxsplit=1)[1].split("\n\n", maxsplit=1)[
        0
    ]
    backend = makefile.split("backend-security-check:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    combined = makefile.split("\nsecurity-check:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]

    assert "node scripts/audit-frontend.mjs" in frontend
    assert "pip_audit --requirement backend/requirements.txt" in backend
    assert "--fix" not in frontend + backend
    assert "$(MAKE) frontend-security-check" in combined
    assert "$(MAKE) backend-security-check" in combined
