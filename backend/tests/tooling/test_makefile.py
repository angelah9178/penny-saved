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
