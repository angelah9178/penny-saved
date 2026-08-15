#!/usr/bin/env python3
"""Build, supervise, and clean up the local end-to-end browser stack."""

from __future__ import annotations

import argparse
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from typing import IO, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from uuid import uuid4

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
FRONTEND_ROOT = REPOSITORY_ROOT / "frontend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.scripts.e2e_data import (  # noqa: E402
    E2EDataConfig,
    E2EDataSafetyError,
    load_config,
    run_cleanup,
    run_setup,
    run_verify_auth_entry,
    run_verify_complete_journey,
)

DEFAULT_FRONTEND_URL = "http://127.0.0.1:4173"
DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
READY_TIMEOUT_SECONDS = 30.0
RUN_TIMEOUT_SECONDS = 120.0
PROCESS_STOP_TIMEOUT_SECONDS = 10.0
MAX_LOG_LINES = 200


class StackError(RuntimeError):
    """Raised when the browser stack cannot be assembled safely."""


class CommandError(StackError):
    """A command failure whose original exit status must be preserved."""

    def __init__(self, message: str, *, exit_status: int) -> None:
        super().__init__(message)
        self.exit_status = exit_status


class ProcessLike(Protocol):
    pid: int

    def poll(self) -> int | None: ...

    def wait(self, timeout: float | None = None) -> int: ...


def redact_log(value: str, secrets_to_remove: Sequence[str]) -> str:
    """Remove configured secrets and common HTTP credential forms from one log line."""
    redacted = value
    for secret in sorted(
        (item for item in secrets_to_remove if item), key=len, reverse=True
    ):
        redacted = redacted.replace(secret, "[REDACTED]")
    patterns = (
        (r"(?i)(authorization\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]"),
        (r"(?i)(cookie\s*[:=]\s*)([^\r\n]+)", r"\1[REDACTED]"),
        (r"(?i)(password\s*[:=]\s*)([^\s,;]+)", r"\1[REDACTED]"),
        (r"postgresql\+psycopg://[^\s]+", "[REDACTED_DATABASE_URL]"),
    )
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted)
    return redacted


@dataclass(slots=True)
class CapturedProcess:
    """One exact child process plus a bounded, already-redacted log tail."""

    name: str
    process: subprocess.Popen[str]
    secrets_to_remove: tuple[str, ...]
    lines: deque[str] = field(default_factory=lambda: deque(maxlen=MAX_LOG_LINES))
    reader: threading.Thread | None = None

    def start_reader(self) -> None:
        stream = self.process.stdout
        if stream is None:
            return

        def consume(output: IO[str]) -> None:
            for line in output:
                self.lines.append(redact_log(line.rstrip(), self.secrets_to_remove))

        self.reader = threading.Thread(target=consume, args=(stream,), daemon=True)
        self.reader.start()


def ensure_loopback_url(name: str, value: str) -> tuple[str, int]:
    """Return host/port only for an exact local HTTP origin."""
    from urllib.parse import urlsplit

    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        or parsed.port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise StackError(
            f"{name} must be an exact loopback HTTP origin with an explicit port."
        )
    return parsed.hostname, parsed.port


def ensure_port_free(host: str, port: int) -> None:
    """Fail without disturbing an unrelated process already using the port."""
    with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET) as candidate:
        candidate.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            candidate.bind((host, port))
        except OSError as error:
            raise StackError(
                f"Refusing E2E startup: {host}:{port} is already in use."
            ) from error


def fetch_text(url: str, timeout: float = 1.0) -> tuple[int, str]:
    """Fetch a readiness resource with a bounded request timeout."""
    try:
        with urlopen(url, timeout=timeout) as response:  # noqa: S310 - loopback URL is validated
            return response.status, response.read(64_000).decode(
                "utf-8", errors="replace"
            )
    except HTTPError as error:
        return error.code, error.read(64_000).decode("utf-8", errors="replace")
    except URLError as error:
        raise ConnectionError(str(error)) from error


def wait_for_readiness(
    processes: Sequence[CapturedProcess],
    checks: Sequence[tuple[str, Callable[[], bool]]],
    *,
    timeout: float = READY_TIMEOUT_SECONDS,
    clock: Callable[[], float] = monotonic,
    wait: Callable[[float], bool] | None = None,
) -> None:
    """Wait for observable readiness while detecting timeout and early exits."""
    wait_for_event = wait or threading.Event().wait
    deadline = clock() + timeout
    remaining = {name: check for name, check in checks}
    while remaining:
        for child in processes:
            status = child.process.poll()
            if status is not None:
                raise StackError(
                    f"{child.name} exited before readiness with status {status}."
                )
        for name, check in tuple(remaining.items()):
            try:
                if check():
                    del remaining[name]
            except (ConnectionError, TimeoutError):
                pass
        if not remaining:
            return
        if clock() >= deadline:
            names = ", ".join(sorted(remaining))
            raise StackError(f"Timed out waiting for E2E readiness: {names}.")
        wait_for_event(0.1)


def stop_process(
    child: ProcessLike,
    *,
    kill_group: Callable[[int, signal.Signals], None] = os.killpg,
    timeout: float = PROCESS_STOP_TIMEOUT_SECONDS,
) -> None:
    """Stop only the process group whose leader is the exact recorded child PID."""
    if child.poll() is not None:
        child.wait()
        return
    kill_group(child.pid, signal.SIGTERM)
    try:
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        kill_group(child.pid, signal.SIGKILL)
        child.wait(timeout=timeout)


def _start_process(
    name: str,
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    secrets_to_remove: tuple[str, ...],
) -> CapturedProcess:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=dict(environment),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    captured = CapturedProcess(name, process, secrets_to_remove)
    captured.start_reader()
    return captured


def _run_checked(
    name: str,
    command: Sequence[str],
    *,
    cwd: Path,
    environment: Mapping[str, str],
    secrets_to_remove: tuple[str, ...],
    failure_log: Path | None = None,
) -> None:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=dict(environment),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        output = redact_log(result.stdout + result.stderr, secrets_to_remove)
        bounded_output = "\n".join(output.splitlines()[-MAX_LOG_LINES:])
        if failure_log is not None:
            failure_log.parent.mkdir(parents=True, exist_ok=True)
            failure_log.write_text(bounded_output + "\n", encoding="utf-8")
        raise CommandError(
            f"{name} failed with status {result.returncode}:\n{bounded_output[-8_000:]}",
            exit_status=result.returncode,
        )


def _generated_environment(
    base: Mapping[str, str],
) -> tuple[dict[str, str], tempfile.TemporaryDirectory[str]]:
    temporary_directory = tempfile.TemporaryDirectory(prefix="penny-saved-e2e-")
    environment = dict(base)
    environment.update(
        {
            "APP_ENV": "test",
            "E2E_FRONTEND_URL": environment.get(
                "E2E_FRONTEND_URL", DEFAULT_FRONTEND_URL
            ),
            "E2E_BACKEND_URL": environment.get("E2E_BACKEND_URL", DEFAULT_BACKEND_URL),
            "E2E_RUN_ID": environment.get(
                "E2E_RUN_ID", f"run-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid4().hex[:8]}"
            ),
            "E2E_EMAIL_DOMAIN": environment.get("E2E_EMAIL_DOMAIN", "browser.invalid"),
            "E2E_PASSWORD": environment.get("E2E_PASSWORD", secrets.token_urlsafe(24)),
            "E2E_SETUP_AT": environment.get(
                "E2E_SETUP_AT", datetime.now(UTC).isoformat()
            ),
            "E2E_MANIFEST_PATH": str(Path(temporary_directory.name) / "manifest.json"),
        }
    )
    return environment, temporary_directory


def _preflight(
    config: E2EDataConfig, environment: dict[str, str]
) -> tuple[str, int, str, int]:
    for tool in ("node", "npm"):
        if shutil.which(tool) is None:
            raise StackError(f"{tool} is required for E2E testing.")
    python = REPOSITORY_ROOT / ".venv" / "bin" / "python"
    if not python.is_file():
        raise StackError(
            "The backend virtual environment is missing; run 'make backend-install'."
        )

    frontend_host, frontend_port = ensure_loopback_url(
        "E2E_FRONTEND_URL", environment["E2E_FRONTEND_URL"]
    )
    backend_host, backend_port = ensure_loopback_url(
        "E2E_BACKEND_URL", environment["E2E_BACKEND_URL"]
    )
    if (frontend_host, frontend_port) == (backend_host, backend_port):
        raise StackError("Frontend and backend E2E origins must use different ports.")
    ensure_port_free(frontend_host, frontend_port)
    ensure_port_free(backend_host, backend_port)
    return frontend_host, frontend_port, backend_host, backend_port


def prepare(config: E2EDataConfig, environment: dict[str, str]) -> None:
    """Validate inputs, migrate the dedicated database, and build the frontend."""
    _preflight(config, environment)
    secrets_to_remove = (config.password, config.database_url)
    artifact_directory = FRONTEND_ROOT / "e2e-artifacts" / config.run_id
    migration_environment = dict(environment)
    migration_environment["DATABASE_URL"] = config.database_url
    _run_checked(
        "E2E migrations",
        [str(REPOSITORY_ROOT / ".venv/bin/python"), "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        environment=migration_environment,
        secrets_to_remove=secrets_to_remove,
        failure_log=artifact_directory / "migrations.log",
    )
    _run_checked(
        "frontend build",
        ["npm", "--prefix", "frontend", "run", "build"],
        cwd=REPOSITORY_ROOT,
        environment=environment,
        secrets_to_remove=secrets_to_remove,
        failure_log=artifact_directory / "frontend-build.log",
    )
    _run_checked(
        "browser test listing",
        ["npm", "--prefix", "frontend", "run", "e2e:list"],
        cwd=REPOSITORY_ROOT,
        environment=environment,
        secrets_to_remove=secrets_to_remove,
        failure_log=artifact_directory / "browser-listing.log",
    )


def _write_failure_logs(
    children: Sequence[CapturedProcess], artifact_directory: Path
) -> None:
    artifact_directory.mkdir(parents=True, exist_ok=True)
    for child in children:
        if child.lines:
            (artifact_directory / f"{child.name}.log").write_text(
                "\n".join(child.lines) + "\n", encoding="utf-8"
            )


def _run_browser_with_live_servers(
    servers: Sequence[CapturedProcess],
    *,
    environment: Mapping[str, str],
    secrets_to_remove: tuple[str, ...],
    failure_log: Path,
) -> None:
    """Run Chromium while failing promptly if either application server exits."""
    playwright_script = environment.get("E2E_PLAYWRIGHT_SCRIPT", "e2e:smoke")
    if playwright_script not in {
        "e2e:contract",
        "e2e:auth-entry",
        "e2e:journey",
        "e2e:acceptance",
        "e2e:smoke",
    }:
        raise StackError("E2E_PLAYWRIGHT_SCRIPT is not an approved browser command.")
    browser = _start_process(
        "browser",
        ["npm", "--prefix", "frontend", "run", playwright_script],
        cwd=REPOSITORY_ROOT,
        environment=environment,
        secrets_to_remove=secrets_to_remove,
    )
    deadline = monotonic() + RUN_TIMEOUT_SECONDS
    while True:
        browser_status = browser.process.poll()
        if browser_status is not None:
            browser.process.wait()
            if browser.reader is not None:
                browser.reader.join(timeout=1.0)
            if browser_status == 0:
                return
            output = "\n".join(browser.lines)
            failure_log.parent.mkdir(parents=True, exist_ok=True)
            failure_log.write_text(output + "\n", encoding="utf-8")
            raise CommandError(
                f"browser contract failed with status {browser_status}:\n{output[-8_000:]}",
                exit_status=browser_status,
            )
        for server in servers:
            status = server.process.poll()
            if status is not None:
                stop_process(browser.process)
                raise StackError(
                    f"{server.name} exited during browser execution with status {status}."
                )
        if monotonic() >= deadline:
            stop_process(browser.process)
            raise StackError("Browser execution exceeded the finite E2E deadline.")
        threading.Event().wait(0.1)


def run_stack(config: E2EDataConfig, environment: dict[str, str]) -> None:
    """Run the complete stack and always stop children and clean run-owned data."""
    frontend_host, frontend_port, backend_host, backend_port = _preflight(
        config, environment
    )
    prepare(config, environment)
    run_setup(config)
    secrets_to_remove = (config.password, config.database_url)
    backend_environment = dict(environment)
    backend_environment.update(
        {
            "DATABASE_URL": config.database_url,
            "FRONTEND_ORIGIN": environment["E2E_FRONTEND_URL"],
            "SESSION_COOKIE_SECURE": "false",
            "TRUSTED_HOSTS": '["localhost","127.0.0.1"]',
            "TRUSTED_PROXY_NETWORKS": "[]",
        }
    )
    children: list[CapturedProcess] = []
    failure: BaseException | None = None
    cleanup_failure: BaseException | None = None
    artifact_directory = FRONTEND_ROOT / "e2e-artifacts" / config.run_id

    def handle_signal(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt(f"E2E run interrupted by signal {signum}")

    previous_handlers = {
        signum: signal.signal(signum, handle_signal)
        for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        children.append(
            _start_process(
                "backend",
                [
                    str(REPOSITORY_ROOT / ".venv/bin/python"),
                    "-m",
                    "uvicorn",
                    "app.main:create_app",
                    "--factory",
                    "--host",
                    backend_host,
                    "--port",
                    str(backend_port),
                ],
                cwd=BACKEND_ROOT,
                environment=backend_environment,
                secrets_to_remove=secrets_to_remove,
            )
        )
        children.append(
            _start_process(
                "frontend",
                [
                    "npm",
                    "--prefix",
                    "frontend",
                    "run",
                    "preview",
                    "--",
                    "--host",
                    frontend_host,
                    "--port",
                    str(frontend_port),
                    "--strictPort",
                ],
                cwd=REPOSITORY_ROOT,
                environment=environment,
                secrets_to_remove=secrets_to_remove,
            )
        )
        wait_for_readiness(
            children,
            (
                (
                    "backend",
                    lambda: (
                        fetch_text(f"{environment['E2E_BACKEND_URL']}/api/ready")[0]
                        == 200
                    ),
                ),
                (
                    "frontend",
                    lambda: (
                        lambda response: (
                            response[0] == 200 and 'id="root"' in response[1]
                        )
                    )(fetch_text(environment["E2E_FRONTEND_URL"])),
                ),
            ),
        )
        _run_browser_with_live_servers(
            children,
            environment=environment,
            secrets_to_remove=secrets_to_remove,
            failure_log=artifact_directory / "browser.log",
        )
        playwright_script = environment.get("E2E_PLAYWRIGHT_SCRIPT", "e2e:smoke")
        default_phase = {
            "e2e:contract": "none",
            "e2e:auth-entry": "auth-entry",
            "e2e:journey": "complete",
            "e2e:acceptance": "none",
            "e2e:smoke": "smoke",
        }[playwright_script]
        verification_phase = environment.get("E2E_VERIFY_PHASE", default_phase)
        if verification_phase in {"auth-entry", "smoke"}:
            run_verify_auth_entry(config)
        if verification_phase in {"complete", "smoke"}:
            run_verify_complete_journey(config)
        if verification_phase not in {"none", "auth-entry", "complete", "smoke"}:
            raise StackError("E2E_VERIFY_PHASE is not an approved verification phase.")
    except BaseException as error:
        failure = error
    finally:
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)
        for child in reversed(children):
            try:
                stop_process(child.process)
            except (OSError, subprocess.SubprocessError) as error:
                cleanup_failure = cleanup_failure or error
            if child.reader is not None:
                child.reader.join(timeout=1.0)
        try:
            run_cleanup(config)
        except BaseException as error:
            cleanup_failure = cleanup_failure or error

    if failure is not None or cleanup_failure is not None:
        _write_failure_logs(children, artifact_directory)
    if failure is not None:
        if cleanup_failure is not None:
            print(f"E2E cleanup also failed: {cleanup_failure}", file=sys.stderr)
        raise failure
    if cleanup_failure is not None:
        raise StackError(f"E2E cleanup failed: {cleanup_failure}") from cleanup_failure


def main(arguments: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "run"))
    args = parser.parse_args(arguments)
    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    try:
        environment, temporary_directory = _generated_environment(os.environ)
        config = load_config(environment)
        if args.operation == "prepare":
            prepare(config, environment)
            print(
                "E2E preflight, migration, frontend build, and browser listing passed."
            )
        else:
            run_stack(config, environment)
            print(f"E2E stack completed and cleaned run {config.run_id}.")
    except CommandError as error:
        print(error, file=sys.stderr)
        return error.exit_status
    except (E2EDataSafetyError, StackError, KeyboardInterrupt) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
