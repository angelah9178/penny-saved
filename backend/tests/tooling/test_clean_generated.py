"""Safety and behavior tests for generated-artifact cleanup."""

from pathlib import Path
from shutil import copy2
from subprocess import run

ROOT = Path(__file__).resolve().parents[3]
CLEAN_SCRIPT = ROOT / "scripts" / "clean-generated.sh"


def _write(path: Path, content: str = "sentinel") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _temporary_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    _write(repository / "Makefile")
    (repository / "backend").mkdir()
    (repository / "frontend").mkdir()
    (repository / "scripts").mkdir()
    copy2(CLEAN_SCRIPT, repository / "scripts" / "clean-generated.sh")
    return repository


def test_cleanup_removes_only_enumerated_generated_artifacts(tmp_path: Path) -> None:
    repository = _temporary_repository(tmp_path)
    generated_paths = [
        repository / "frontend" / "dist" / "index.html",
        repository / "frontend" / "coverage" / "index.html",
        repository / "frontend" / "tsconfig.app.tsbuildinfo",
        repository / "frontend" / "tsconfig.node.tsbuildinfo",
        repository / "backend" / ".pytest_cache" / "state",
        repository / "backend" / ".ruff_cache" / "state",
        repository / "backend" / "htmlcov" / "index.html",
        repository / "backend" / ".coverage",
        repository / "backend" / "app" / "__pycache__" / "module.cpython.pyc",
        repository / "backend" / "tests" / "test_module.pyo",
        repository / "backend" / "alembic" / "__pycache__" / "env.cpython.pyc",
    ]
    preserved_paths = [
        repository / "frontend" / "src" / "main.tsx",
        repository / "frontend" / "node_modules" / "package" / "index.js",
        repository / "frontend" / ".env",
        repository / "backend" / "app" / "main.py",
        repository / "backend" / "tests" / "test_main.py",
        repository / "backend" / "alembic" / "versions" / "0001_initial_schema.py",
        repository / "backend" / ".env",
        repository / ".venv" / "bin" / "python",
        repository / ".git" / "HEAD",
        repository / "development" / "DEV-006.md",
        repository / "docker-volume-sentinel",
    ]
    for path in generated_paths + preserved_paths:
        _write(path)

    run(["bash", repository / "scripts" / "clean-generated.sh"], check=True)

    assert all(not path.exists() for path in generated_paths)
    assert all(path.exists() for path in preserved_paths)


def test_cleanup_is_safe_to_run_repeatedly(tmp_path: Path) -> None:
    repository = _temporary_repository(tmp_path)
    script = repository / "scripts" / "clean-generated.sh"

    run(["bash", script], check=True)
    run(["bash", script], check=True)


def test_cleanup_refuses_an_unrecognized_directory(tmp_path: Path) -> None:
    directory = tmp_path / "not-a-repository"
    script = directory / "scripts" / "clean-generated.sh"
    script.parent.mkdir(parents=True)
    copy2(CLEAN_SCRIPT, script)

    result = run(["bash", script], check=False, capture_output=True, text=True)

    assert result.returncode != 0
    assert "Refusing cleanup" in result.stderr
