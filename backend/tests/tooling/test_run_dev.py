"""Process-level tests for coordinated development server supervision."""

from __future__ import annotations

import os
import signal
from pathlib import Path
from shutil import copy2
from subprocess import PIPE, Popen, run
from time import monotonic, sleep

import pytest

ROOT = Path(__file__).resolve().parents[3]
RUN_DEV_SCRIPT = ROOT / "scripts" / "run-dev.sh"


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    path.chmod(0o755)


def _temporary_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    scripts = repository / "scripts"
    scripts.mkdir(parents=True)
    (repository / "Makefile").write_text("sentinel")
    copy2(RUN_DEV_SCRIPT, scripts / "run-dev.sh")

    fake_bin = tmp_path / "bin"
    _write_executable(
        fake_bin / "make",
        """#!/usr/bin/env bash
set -euo pipefail
target=${!#}
case "$target" in
  backend-dev) exec "$FAKE_BACKEND" ;;
  frontend-dev) exec "$FAKE_FRONTEND" ;;
  *) exit 64 ;;
esac
""",
    )
    return repository, fake_bin


def _environment(fake_bin: Path, backend: Path, frontend: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "FAKE_BACKEND": str(backend),
            "FAKE_FRONTEND": str(frontend),
        }
    )
    return environment


def _wait_for_files(paths: list[Path], timeout: float = 5) -> None:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        if all(path.exists() for path in paths):
            return
        sleep(0.01)
    pytest.fail(f"Timed out waiting for process markers: {paths}")


def _assert_process_stopped(pid_file: Path) -> None:
    process_id = int(pid_file.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(process_id, 0)


def test_supervisor_propagates_failure_and_stops_the_sibling(tmp_path: Path) -> None:
    repository, fake_bin = _temporary_repository(tmp_path)
    backend = tmp_path / "backend"
    frontend = tmp_path / "frontend"
    frontend_started = tmp_path / "frontend-started"
    frontend_stopped = tmp_path / "frontend-stopped"
    frontend_pid = tmp_path / "frontend-pid"
    _write_executable(
        backend,
        """#!/usr/bin/env bash
sleep 0.2
exit 23
""",
    )
    _write_executable(
        frontend,
        f"""#!/usr/bin/env bash
set -euo pipefail
trap 'touch "{frontend_stopped}"; exit 0' TERM
echo "$BASHPID" > "{frontend_pid}"
touch "{frontend_started}"
while true; do sleep 0.1; done
""",
    )

    result = run(
        ["bash", repository / "scripts" / "run-dev.sh"],
        env=_environment(fake_bin, backend, frontend),
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 23
    assert frontend_started.exists()
    assert frontend_stopped.exists()
    _assert_process_stopped(frontend_pid)


def test_supervisor_forwards_termination_and_reaps_both_servers(tmp_path: Path) -> None:
    repository, fake_bin = _temporary_repository(tmp_path)
    stopped_paths: list[Path] = []
    pid_paths: list[Path] = []
    child_paths: list[Path] = []

    for name in ("backend", "frontend"):
        child = tmp_path / name
        started = tmp_path / f"{name}-started"
        stopped = tmp_path / f"{name}-stopped"
        pid_file = tmp_path / f"{name}-pid"
        _write_executable(
            child,
            f"""#!/usr/bin/env bash
set -euo pipefail
trap 'touch "{stopped}"; exit 0' TERM
echo "$BASHPID" > "{pid_file}"
touch "{started}"
while true; do sleep 0.1; done
""",
        )
        child_paths.append(child)
        stopped_paths.append(stopped)
        pid_paths.append(pid_file)

    process = Popen(
        ["bash", repository / "scripts" / "run-dev.sh"],
        env=_environment(fake_bin, child_paths[0], child_paths[1]),
        stdout=PIPE,
        stderr=PIPE,
        text=True,
    )
    _wait_for_files(pid_paths)
    process.send_signal(signal.SIGTERM)

    assert process.wait(timeout=5) == 143
    assert all(path.exists() for path in stopped_paths)
    for pid_file in pid_paths:
        _assert_process_stopped(pid_file)
