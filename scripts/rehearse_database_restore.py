"""Rehearse backup and restore against one guarded disposable local database."""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import URL, make_url

TARGET_DATABASE = "penny_saved_dev022_restore_verify"
REPRESENTATIVE_TABLES = ("users", "impulse_purchase_entries", "sessions")
ROOT = Path(__file__).resolve().parents[1]


def validate_source_url(raw_url: str) -> URL:
    """Allow only the dedicated loopback PostgreSQL test database."""
    url = make_url(raw_url)
    if url.drivername != "postgresql+psycopg":
        raise ValueError("TEST_DATABASE_URL must use postgresql+psycopg")
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Restore rehearsal requires a loopback PostgreSQL host")
    if not url.database or not url.database.endswith("_test"):
        raise ValueError("Restore rehearsal requires a database name ending in _test")
    if url.database == TARGET_DATABASE:
        raise ValueError("Source and disposable restore databases must differ")
    return url


def connection_parameters(url: URL, *, database: str) -> dict[str, object]:
    """Build psycopg parameters without rendering credentials into a command."""
    return {
        "host": url.host,
        "port": url.port or 5432,
        "user": url.username,
        "password": url.password,
        "dbname": database,
    }


def database_exists(connection: psycopg.Connection[object], database: str) -> bool:
    """Return whether one exact database name already exists."""
    row = connection.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (database,),
    ).fetchone()
    return row is not None


def table_counts(connection: psycopg.Connection[object]) -> dict[str, int]:
    """Read only the approved representative table counts."""
    return {
        table: int(
            connection.execute(
                sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))
            ).fetchone()[0]
        )
        for table in REPRESENTATIVE_TABLES
    }


def rehearse(raw_url: str) -> dict[str, object]:
    """Dump, restore, verify, and remove the fixed disposable target."""
    source_url = validate_source_url(raw_url)
    admin_parameters = connection_parameters(source_url, database="postgres")
    source_parameters = connection_parameters(
        source_url, database=str(source_url.database)
    )
    target_parameters = connection_parameters(source_url, database=TARGET_DATABASE)

    with psycopg.connect(**admin_parameters, autocommit=True) as admin:
        if database_exists(admin, TARGET_DATABASE):
            raise RuntimeError(
                f"Refusing to overwrite existing database {TARGET_DATABASE}; inspect it manually"
            )

        with tempfile.TemporaryDirectory(
            prefix="penny-saved-dev022-restore-"
        ) as temp_directory:
            backup_path = Path(temp_directory) / "test-database.dump"
            with backup_path.open("wb") as backup_file:
                subprocess.run(
                    [
                        "docker",
                        "compose",
                        "exec",
                        "-T",
                        "postgres",
                        "pg_dump",
                        f"--username={source_url.username}",
                        f"--dbname={source_url.database}",
                        "--format=custom",
                        "--no-owner",
                        "--no-acl",
                    ],
                    check=True,
                    cwd=ROOT,
                    stdout=backup_file,
                )
            subprocess.run(
                ["pg_restore", "--list", str(backup_path)],
                check=True,
                capture_output=True,
            )
            checksum = hashlib.sha256(backup_path.read_bytes()).hexdigest()

            with psycopg.connect(**source_parameters) as source:
                source_revision = source.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()[0]
                source_counts = table_counts(source)

            admin.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(TARGET_DATABASE))
            )
            try:
                with backup_path.open("rb") as backup_file:
                    subprocess.run(
                        [
                            "docker",
                            "compose",
                            "exec",
                            "-T",
                            "postgres",
                            "pg_restore",
                            f"--username={source_url.username}",
                            f"--dbname={TARGET_DATABASE}",
                            "--exit-on-error",
                            "--no-owner",
                            "--no-acl",
                        ],
                        check=True,
                        cwd=ROOT,
                        stdin=backup_file,
                    )
                with psycopg.connect(**target_parameters) as target:
                    target_revision = target.execute(
                        "SELECT version_num FROM alembic_version"
                    ).fetchone()[0]
                    target_counts = table_counts(target)
                if target_revision != source_revision or target_counts != source_counts:
                    raise RuntimeError(
                        "Restored migration revision or representative counts differ"
                    )
                return {
                    "source_database": source_url.database,
                    "target_database": TARGET_DATABASE,
                    "migration_revision": target_revision,
                    "representative_counts": target_counts,
                    "backup_sha256": checksum,
                }
            finally:
                admin.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()",
                    (TARGET_DATABASE,),
                )
                admin.execute(
                    sql.SQL("DROP DATABASE {}").format(sql.Identifier(TARGET_DATABASE))
                )


def main() -> int:
    if os.environ.get("ALLOW_DISPOSABLE_RESTORE_REHEARSAL") != "yes":
        raise SystemExit(
            "Set ALLOW_DISPOSABLE_RESTORE_REHEARSAL=yes to confirm the local rehearsal"
        )
    raw_url = os.environ.get("TEST_DATABASE_URL")
    if not raw_url:
        raise SystemExit("TEST_DATABASE_URL is required")
    evidence = rehearse(raw_url)
    print("Disposable backup/restore rehearsal passed.")
    print(f"Source database: {evidence['source_database']}")
    print(f"Disposable target removed: {evidence['target_database']}")
    print(f"Migration revision: {evidence['migration_revision']}")
    print(f"Representative counts: {evidence['representative_counts']}")
    print(f"Backup SHA-256: {evidence['backup_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
