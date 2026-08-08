"""Tooling contracts for the browser-stack supervisor."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import e2e_stack  # noqa: E402
from e2e_stack import (  # noqa: E402
    CommandError,
    StackError,
    _run_browser_with_live_servers,
    _run_checked,
    ensure_loopback_url,
    ensure_port_free,
    redact_log,
    stop_process,
    wait_for_readiness,
)


class _FakeProcess:
    def __init__(self, *, pid: int = 4321, status: int | None = None) -> None:
        self.pid = pid
        self.status = status
        self.wait_calls: list[float | None] = []

    def poll(self) -> int | None:
        return self.status

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        self.status = 0
        return 0


def _captured(name: str, process: _FakeProcess) -> SimpleNamespace:
    return SimpleNamespace(name=name, process=process)


def test_only_exact_loopback_origins_are_accepted() -> None:
    assert ensure_loopback_url("frontend", "http://127.0.0.1:4173") == (
        "127.0.0.1",
        4173,
    )

    for unsafe in (
        "https://stopimpulsebuying.us",
        "http://example.com:4173",
        "http://127.0.0.1:4173/path",
        "http://user:secret@127.0.0.1:4173",
    ):
        with pytest.raises(StackError, match="loopback"):
            ensure_loopback_url("frontend", unsafe)


def test_occupied_port_is_rejected_without_touching_listener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _OccupiedCandidate:
        closed = False

        def __enter__(self) -> _OccupiedCandidate:
            return self

        def __exit__(self, *_args: object) -> None:
            self.closed = True

        def setsockopt(self, *_args: object) -> None:
            pass

        def bind(self, _address: tuple[str, int]) -> None:
            raise OSError("occupied")

    candidate = _OccupiedCandidate()
    monkeypatch.setattr(e2e_stack.socket, "socket", lambda *_args: candidate)

    with pytest.raises(StackError, match="already in use"):
        ensure_port_free("127.0.0.1", 4173)
    assert candidate.closed


def test_readiness_uses_observable_checks_and_detects_early_exit() -> None:
    process = _FakeProcess(status=None)
    observations = iter((False, True))

    wait_for_readiness(
        [_captured("backend", process)],
        [("backend", lambda: next(observations))],
        wait=lambda _duration: False,
    )

    process.status = 17
    with pytest.raises(StackError, match="status 17"):
        wait_for_readiness(
            [_captured("backend", process)],
            [("backend", lambda: False)],
        )


def test_readiness_timeout_is_bounded_without_a_fixed_sleep() -> None:
    clock_values = iter((0.0, 2.0))
    with pytest.raises(StackError, match="Timed out.*frontend"):
        wait_for_readiness(
            [_captured("frontend", _FakeProcess())],
            [("frontend", lambda: False)],
            timeout=1.0,
            clock=lambda: next(clock_values),
            wait=lambda _duration: False,
        )


def test_logs_redact_database_password_cookie_and_authorization() -> None:
    database_url = "postgresql+psycopg://user:db-secret@localhost/app_e2e_test"
    output = redact_log(
        f"url={database_url} password=browser-secret Cookie=session=abc Authorization=Bearer-token",
        (database_url, "browser-secret"),
    )

    for secret in (database_url, "db-secret", "browser-secret", "session=abc", "Bearer-token"):
        assert secret not in output
    assert "[REDACTED]" in output


def test_failed_command_preserves_status_and_writes_only_redacted_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        e2e_stack.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=23,
            stdout="password=browser-secret\n",
            stderr="Authorization=token-value\n",
        ),
    )
    failure_log = tmp_path / "browser.log"

    with pytest.raises(CommandError) as raised:
        _run_checked(
            "browser",
            ["browser"],
            cwd=tmp_path,
            environment={},
            secrets_to_remove=("browser-secret",),
            failure_log=failure_log,
        )

    assert raised.value.exit_status == 23
    assert "browser-secret" not in failure_log.read_text(encoding="utf-8")
    assert "token-value" not in failure_log.read_text(encoding="utf-8")


def test_stop_targets_only_the_recorded_process_group() -> None:
    process = _FakeProcess(pid=9876)
    signals: list[tuple[int, signal.Signals]] = []

    stop_process(process, kill_group=lambda pid, sent: signals.append((pid, sent)))

    assert signals == [(9876, signal.SIGTERM)]
    assert process.wait_calls == [10.0]


def test_server_exit_stops_browser_sibling_immediately(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _captured("backend", _FakeProcess(status=19))
    browser_process = _FakeProcess(status=None)
    browser = SimpleNamespace(
        name="browser",
        process=browser_process,
        reader=None,
        lines=[],
    )
    stopped: list[int] = []
    monkeypatch.setattr(e2e_stack, "_start_process", lambda *_args, **_kwargs: browser)
    monkeypatch.setattr(
        e2e_stack,
        "stop_process",
        lambda process: stopped.append(process.pid),
    )

    with pytest.raises(StackError, match="backend exited during browser"):
        _run_browser_with_live_servers(
            [server],
            environment={},
            secrets_to_remove=(),
            failure_log=tmp_path / "browser.log",
        )

    assert stopped == [browser_process.pid]


def test_real_child_group_is_reaped_without_an_orphan() -> None:
    process = subprocess.Popen(
        [sys.executable, "-c", "import signal; signal.pause()"],
        start_new_session=True,
    )
    stop_process(process)

    assert process.poll() is not None
    with pytest.raises(ProcessLookupError):
        os.kill(process.pid, 0)


def test_makefile_exposes_reusable_e2e_commands() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    for target in ("e2e-prepare", "e2e", "e2e-auth-entry", "e2e-cleanup-check"):
        assert f"{target}:" in makefile
    e2e_recipe = makefile.split("\ne2e:", maxsplit=1)[1].split("\n\n", maxsplit=1)[0]
    assert "scripts/e2e_stack.py run" in e2e_recipe
    assert "E2E_DATABASE_URL" in e2e_recipe
    assert "db-reset" not in e2e_recipe
