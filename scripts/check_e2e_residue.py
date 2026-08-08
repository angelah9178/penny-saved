#!/usr/bin/env python3
"""Fail when a dedicated browser-test database or port retains E2E state."""

from __future__ import annotations

import os
import socket
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPOSITORY_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine, func, select  # noqa: E402

from app.models.entry import ImpulsePurchaseEntry  # noqa: E402
from app.models.opportunity_cost_example import OpportunityCostExample  # noqa: E402
from app.models.session import Session  # noqa: E402
from app.models.user import User  # noqa: E402
from app.scripts.e2e_data import E2EDataSafetyError, validate_database_target  # noqa: E402


def _assert_port_free(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} or parsed.port is None:
        raise E2EDataSafetyError(
            "Residue checks require explicit loopback URLs and ports."
        )
    family = socket.AF_INET6 if parsed.hostname == "::1" else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((parsed.hostname, parsed.port))
        except OSError as error:
            raise E2EDataSafetyError(
                f"E2E process still owns {parsed.hostname}:{parsed.port}."
            ) from error


def main() -> int:
    database_url = os.environ.get("E2E_DATABASE_URL", "")
    validate_database_target(database_url, environment=os.environ)
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            counts = {
                "users": connection.scalar(select(func.count()).select_from(User)),
                "sessions": connection.scalar(
                    select(func.count()).select_from(Session)
                ),
                "entries": connection.scalar(
                    select(func.count()).select_from(ImpulsePurchaseEntry)
                ),
                "opportunity-cost examples": connection.scalar(
                    select(func.count()).select_from(OpportunityCostExample)
                ),
            }
    finally:
        engine.dispose()
    remaining = {name: count for name, count in counts.items() if count}
    if remaining:
        details = ", ".join(f"{name}={count}" for name, count in remaining.items())
        raise E2EDataSafetyError(f"Dedicated E2E database retained state: {details}.")

    _assert_port_free(os.environ.get("E2E_FRONTEND_URL", ""))
    _assert_port_free(os.environ.get("E2E_BACKEND_URL", ""))
    temporary_runs = list(Path(tempfile.gettempdir()).glob("penny-saved-e2e-*"))
    if temporary_runs:
        raise E2EDataSafetyError("E2E run left a temporary manifest directory behind.")
    print("E2E database and application ports are clean.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except E2EDataSafetyError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error
