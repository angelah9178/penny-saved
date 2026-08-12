"""Static validation for secret-free production operations examples."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = ROOT / "operations"
ENV_EXAMPLE = OPERATIONS / "production.env.example"
NGINX_EXAMPLE = OPERATIONS / "nginx" / "penny-saved.conf.example"
SYSTEMD_EXAMPLE = OPERATIONS / "systemd" / "penny-saved.service.example"
RUNBOOK = OPERATIONS / "README.md"
RELEASE_DECISIONS = ROOT / "development" / "release-decisions.md"

REQUIRED_ENVIRONMENT_NAMES = {
    "APP_ENV",
    "DATABASE_URL",
    "FRONTEND_ORIGIN",
    "SESSION_COOKIE_SECURE",
    "LOG_LEVEL",
    "LOG_FORMAT",
    "HEALTH_CHECK_TIMEOUT_SECONDS",
    "METRICS_ENABLED",
    "GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS",
    "TRUSTED_HOSTS",
    "TRUSTED_PROXY_NETWORKS",
    "MAX_REQUEST_BODY_BYTES",
    "RATE_LIMIT_KEY_SECRET",
}
REQUIRED_DECISION_FIELDS = {
    "id",
    "question",
    "owner",
    "decision",
    "evidence",
    "source",
    "deadline",
    "status",
}
SECRET_PATTERNS = (
    re.compile(r"postgresql(?:\+psycopg)?://[^\s:@]+:[^\s@]+@", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\b(?:password|token|secret)\s*[:=]\s*[^\s,]+", re.IGNORECASE),
)


def parse_release_decisions(text: str) -> list[dict[str, str]]:
    """Parse fixed Markdown headings and labeled bullets into decision records."""
    decisions: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    current_field: str | None = None
    for line in text.splitlines():
        heading = re.fullmatch(r"## ([a-z0-9-]+) — (.+)", line)
        if heading:
            current = {"id": heading[1], "question": heading[2]}
            decisions.append(current)
            current_field = None
            continue
        field = re.fullmatch(
            r"- (Owner|Decision|Evidence|Source|Deadline|Status):\s*(.*)", line
        )
        if field and current is not None:
            current_field = field[1].lower()
            current[current_field] = field[2]
            continue
        if not line.strip():
            current_field = None
        elif current is not None and current_field is not None:
            current[current_field] = f"{current[current_field]} {line.strip()}"
    return decisions


def validate_release_decisions(
    decisions: list[dict[str, str]], *, today: date | None = None
) -> list[str]:
    """Validate owners, evidence, status, deadlines, uniqueness, and secret safety."""
    errors: list[str] = []
    current_date = today or datetime.now(UTC).date()
    allowed_statuses = {"ready", "deferred", "blocked"}
    if not decisions:
        return ["Release decisions must contain at least one decision section"]

    seen_ids: set[str] = set()
    for index, item in enumerate(decisions, start=1):
        missing = REQUIRED_DECISION_FIELDS - item.keys()
        if missing:
            errors.append(
                f"Release decision {index} is missing: {', '.join(sorted(missing))}"
            )
            continue
        decision_id = item["id"]
        if not re.fullmatch(r"[a-z0-9-]+", decision_id):
            errors.append(f"Release decision {index} has an invalid ID")
            continue
        if decision_id in seen_ids:
            errors.append(f"Duplicate release decision ID: {decision_id}")
        seen_ids.add(decision_id)
        for field in REQUIRED_DECISION_FIELDS - {"id"}:
            if not item[field].strip():
                errors.append(f"Release decision {decision_id} has a blank {field}")
        if item["status"] not in allowed_statuses:
            errors.append(f"Release decision {decision_id} has an invalid status")
        deadline = item["deadline"]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline):
            if date.fromisoformat(deadline) < current_date:
                errors.append(f"Release decision {decision_id} has an expired deadline")
        serialized = "\n".join(item.values())
        if any(pattern.search(serialized) for pattern in SECRET_PATTERNS):
            errors.append(
                f"Release decision {decision_id} contains secret-like material"
            )
    return errors


def parse_environment_example(text: str) -> dict[str, str]:
    """Parse the restricted NAME=value syntax used by the example."""
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid environment line {line_number}")
        name, value = line.split("=", maxsplit=1)
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name) or not value:
            raise ValueError(f"Invalid environment assignment on line {line_number}")
        if name in values:
            raise ValueError(f"Duplicate environment variable: {name}")
        values[name] = value
    return values


def validate() -> list[str]:
    """Return every static validation failure without changing any file."""
    errors: list[str] = []
    required_files = (
        ENV_EXAMPLE,
        NGINX_EXAMPLE,
        SYSTEMD_EXAMPLE,
        RUNBOOK,
        RELEASE_DECISIONS,
    )
    for path in required_files:
        if not path.is_file():
            errors.append(f"Missing operations file: {path.relative_to(ROOT)}")
    if errors:
        return errors

    environment_text = ENV_EXAMPLE.read_text()
    try:
        environment = parse_environment_example(environment_text)
    except ValueError as error:
        errors.append(str(error))
        environment = {}
    missing_names = REQUIRED_ENVIRONMENT_NAMES - environment.keys()
    if missing_names:
        errors.append(
            f"Missing environment variables: {', '.join(sorted(missing_names))}"
        )
    if environment.get("APP_ENV") != "production":
        errors.append("APP_ENV must be production")
    if environment.get("FRONTEND_ORIGIN") != "https://stopimpulsebuying.us":
        errors.append("FRONTEND_ORIGIN must use the approved canonical HTTPS origin")
    if environment.get("SESSION_COOKIE_SECURE") != "true":
        errors.append("Production session cookies must be secure")
    if environment.get("LOG_FORMAT") != "json":
        errors.append("Production logs must use JSON")
    for secret_name in ("DATABASE_URL", "RATE_LIMIT_KEY_SECRET"):
        if "REPLACE_WITH" not in environment.get(secret_name, ""):
            errors.append(f"{secret_name} must retain an obvious placeholder")

    release_decisions = parse_release_decisions(RELEASE_DECISIONS.read_text())
    errors.extend(validate_release_decisions(release_decisions))

    combined = "\n".join(path.read_text() for path in required_files)
    forbidden_values = (
        "change-me-for-local-development",
        "development-only-rate-limit-key-secret",
        "BEGIN PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
    )
    for forbidden in forbidden_values:
        if forbidden in combined:
            errors.append(
                f"Operations examples contain forbidden secret material: {forbidden}"
            )

    nginx = NGINX_EXAMPLE.read_text()
    for fragment in (
        "server_name stopimpulsebuying.us",
        "proxy_pass http://127.0.0.1:8000",
        "proxy_set_header X-Forwarded-For",
        "proxy_set_header X-Forwarded-Proto https",
        "client_max_body_size 1m",
        "try_files $uri $uri/ /index.html",
        "location = /internal/metrics",
        "return 404",
    ):
        if fragment not in nginx:
            errors.append(f"Nginx example is missing: {fragment}")

    systemd = SYSTEMD_EXAMPLE.read_text()
    for fragment in (
        "User=penny-saved",
        "EnvironmentFile=/etc/penny-saved/backend.env",
        "--host 127.0.0.1",
        "--no-proxy-headers",
        "Restart=on-failure",
        "KillSignal=SIGTERM",
        "TimeoutStopSec=40s",
        "NoNewPrivileges=true",
    ):
        if fragment not in systemd:
            errors.append(f"systemd example is missing: {fragment}")
    if "alembic" in systemd.lower():
        errors.append("The service must not apply migrations during ordinary startup")

    runbook = RUNBOOK.read_text()
    for heading in (
        "## Required Decisions Before Release",
        "## Production Configuration",
        "## Reverse Proxy and TLS",
        "## Process Supervisor",
        "## Health, Metrics, and Logs",
        "## Database-Outage Response",
        "## Backup Procedure",
        "## Isolated Restore Verification",
        "## Rollback Boundary",
    ):
        if heading not in runbook:
            errors.append(f"Runbook is missing: {heading}")
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Production operations examples passed static validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
