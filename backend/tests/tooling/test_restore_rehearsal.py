"""Guard tests for the disposable database restore rehearsal."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "rehearse_database_restore.py"


def _load_script() -> object:
    spec = importlib.util.spec_from_file_location("rehearse_database_restore", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "sqlite:///test.sqlite3",
        "postgresql+psycopg://app:secret@database.example/penny_saved_test",
        "postgresql+psycopg://app:secret@localhost/penny_saved",
        "postgresql+psycopg://app:secret@localhost/penny_saved_dev022_restore_verify",
    ],
)
def test_restore_rehearsal_rejects_unsafe_source(unsafe_url: str) -> None:
    script = _load_script()

    with pytest.raises(ValueError):
        script.validate_source_url(unsafe_url)


def test_restore_rehearsal_accepts_only_loopback_test_database() -> None:
    script = _load_script()

    url = script.validate_source_url(
        "postgresql+psycopg://app:secret@127.0.0.1:5433/penny_saved_test"
    )

    assert url.database == "penny_saved_test"
    assert script.TARGET_DATABASE == "penny_saved_dev022_restore_verify"
