"""Stable production observability and operations contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MetricType(StrEnum):
    """Metric shapes supported by the operational contract."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True)
class MetricContract:
    """A bounded metric definition that later instrumentation must preserve."""

    name: str
    metric_type: MetricType
    unit: str
    labels: tuple[str, ...]
    purpose: str


@dataclass(frozen=True)
class HealthContract:
    """A stable health endpoint response and dependency contract."""

    path: str
    success_status: int
    failure_status: int | None
    depends_on_database: bool
    success_body: tuple[tuple[str, str], ...]
    failure_body: tuple[tuple[str, str], ...] | None


REQUEST_ID_HEADER = "X-Request-ID"
REQUEST_ID_FORMAT = "canonical UUID"
REQUEST_ID_MAX_LENGTH = 36
UNMATCHED_ROUTE_TEMPLATE = "unmatched"
METRICS_PATH = "/internal/metrics"

STRUCTURED_LOG_REQUIRED_FIELDS = frozenset(
    {
        "timestamp",
        "level",
        "environment",
        "event",
        "request_id",
        "method",
        "route",
        "status",
        "duration_ms",
    }
)
STRUCTURED_LOG_OPTIONAL_FIELDS = frozenset({"user_id", "context"})
FORBIDDEN_OBSERVABILITY_VALUES = frozenset(
    {
        "authorization",
        "cookie",
        "database_url",
        "email",
        "entry_id",
        "password",
        "query_string",
        "raw_path",
        "request_body",
        "request_id_label",
        "session_token",
        "user_id_label",
    }
)

METRIC_CONTRACTS = (
    MetricContract(
        name="http_server_requests_total",
        metric_type=MetricType.COUNTER,
        unit="requests",
        labels=("method", "route", "status_class"),
        purpose="Measure request volume and status trends.",
    ),
    MetricContract(
        name="http_server_request_duration_seconds",
        metric_type=MetricType.HISTOGRAM,
        unit="seconds",
        labels=("method", "route"),
        purpose="Measure request latency by stable route template.",
    ),
    MetricContract(
        name="http_server_errors_total",
        metric_type=MetricType.COUNTER,
        unit="errors",
        labels=("method", "route", "status_class"),
        purpose="Measure server and safe client error trends.",
    ),
    MetricContract(
        name="database_pool_connections",
        metric_type=MetricType.GAUGE,
        unit="connections",
        labels=("state",),
        purpose="Show bounded database connection-pool utilization.",
    ),
    MetricContract(
        name="authentication_failures_total",
        metric_type=MetricType.COUNTER,
        unit="failures",
        labels=("operation", "reason"),
        purpose="Measure aggregate login and signup failure trends.",
    ),
    MetricContract(
        name="entry_lifecycle_conflicts_total",
        metric_type=MetricType.COUNTER,
        unit="conflicts",
        labels=("operation",),
        purpose="Measure aggregate entry state-transition conflicts.",
    ),
    MetricContract(
        name="application_readiness",
        metric_type=MetricType.GAUGE,
        unit="state",
        labels=(),
        purpose="Report one for ready and zero for unavailable.",
    ),
)

LIVENESS_CONTRACT = HealthContract(
    path="/api/health",
    success_status=200,
    failure_status=None,
    depends_on_database=False,
    success_body=(("status", "ok"),),
    failure_body=None,
)
READINESS_CONTRACT = HealthContract(
    path="/api/ready",
    success_status=200,
    failure_status=503,
    depends_on_database=True,
    success_body=(("status", "ready"),),
    failure_body=(("status", "unavailable"),),
)
