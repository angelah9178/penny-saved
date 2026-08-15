"""Privacy-bounded in-process operational metrics."""

from __future__ import annotations

from collections import defaultdict
from threading import Lock
from time import perf_counter

from app.core.logging import get_route_template
from app.core.operations import METRICS_PATH
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_DURATION_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


class MetricsRegistry:
    """Store only the fixed metric names and bounded labels approved by DEV-022."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._requests: defaultdict[tuple[str, str, str], int] = defaultdict(int)
        self._errors: defaultdict[tuple[str, str, str], int] = defaultdict(int)
        self._duration_count: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._duration_sum: defaultdict[tuple[str, str], float] = defaultdict(float)
        self._duration_buckets: defaultdict[tuple[str, str, float], int] = defaultdict(int)
        self._auth_failures: defaultdict[tuple[str, str], int] = defaultdict(int)
        self._lifecycle_conflicts: defaultdict[str, int] = defaultdict(int)
        self._readiness = 0

    def observe_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_seconds: float,
    ) -> None:
        """Record one completed request using bounded HTTP dimensions."""
        normalized_method = _bounded_method(method)
        status_class = _status_class(status_code)
        request_key = (normalized_method, route, status_class)
        duration_key = (normalized_method, route)
        with self._lock:
            self._requests[request_key] += 1
            self._duration_count[duration_key] += 1
            self._duration_sum[duration_key] += duration_seconds
            for bucket in _DURATION_BUCKETS:
                if duration_seconds <= bucket:
                    self._duration_buckets[(*duration_key, bucket)] += 1
            if status_code >= 400:
                self._errors[request_key] += 1

    def record_authentication_failure(self, *, operation: str, reason: str) -> None:
        """Record one failure after its operation and reason are safely mapped."""
        with self._lock:
            self._auth_failures[(operation, reason)] += 1

    def record_lifecycle_conflict(self, *, operation: str) -> None:
        """Record one entry conflict using a bounded operation name."""
        with self._lock:
            self._lifecycle_conflicts[operation] += 1

    def set_readiness(self, ready: bool) -> None:
        """Publish the most recently observed readiness state."""
        with self._lock:
            self._readiness = int(ready)

    def render(self, *, database_pool: object | None = None) -> str:
        """Render a deterministic Prometheus text exposition snapshot."""
        with self._lock:
            requests = dict(self._requests)
            errors = dict(self._errors)
            duration_count = dict(self._duration_count)
            duration_sum = dict(self._duration_sum)
            duration_buckets = dict(self._duration_buckets)
            auth_failures = dict(self._auth_failures)
            lifecycle_conflicts = dict(self._lifecycle_conflicts)
            readiness = self._readiness

        lines = [
            "# HELP http_server_requests_total Completed HTTP requests.",
            "# TYPE http_server_requests_total counter",
        ]
        for labels, value in sorted(requests.items()):
            lines.append(_sample("http_server_requests_total", _http_labels(labels), value))

        lines.extend(
            [
                "# HELP http_server_request_duration_seconds HTTP request duration.",
                "# TYPE http_server_request_duration_seconds histogram",
            ]
        )
        for method, route in sorted(duration_count):
            base_labels = {"method": method, "route": route}
            for bucket in _DURATION_BUCKETS:
                count = duration_buckets.get((method, route, bucket), 0)
                lines.append(
                    _sample(
                        "http_server_request_duration_seconds_bucket",
                        {**base_labels, "le": _number(bucket)},
                        count,
                    )
                )
            lines.append(
                _sample(
                    "http_server_request_duration_seconds_bucket",
                    {**base_labels, "le": "+Inf"},
                    duration_count[(method, route)],
                )
            )
            lines.append(
                _sample(
                    "http_server_request_duration_seconds_sum",
                    base_labels,
                    duration_sum[(method, route)],
                )
            )
            lines.append(
                _sample(
                    "http_server_request_duration_seconds_count",
                    base_labels,
                    duration_count[(method, route)],
                )
            )

        lines.extend(
            [
                "# HELP http_server_errors_total Completed HTTP error responses.",
                "# TYPE http_server_errors_total counter",
            ]
        )
        for labels, value in sorted(errors.items()):
            lines.append(_sample("http_server_errors_total", _http_labels(labels), value))

        lines.extend(
            [
                "# HELP database_pool_connections Database connections by bounded state.",
                "# TYPE database_pool_connections gauge",
            ]
        )
        for state, value in _database_pool_values(database_pool).items():
            lines.append(_sample("database_pool_connections", {"state": state}, value))

        lines.extend(
            [
                "# HELP authentication_failures_total Authentication failures.",
                "# TYPE authentication_failures_total counter",
            ]
        )
        for (operation, reason), value in sorted(auth_failures.items()):
            lines.append(
                _sample(
                    "authentication_failures_total",
                    {"operation": operation, "reason": reason},
                    value,
                )
            )

        lines.extend(
            [
                "# HELP entry_lifecycle_conflicts_total Entry lifecycle conflicts.",
                "# TYPE entry_lifecycle_conflicts_total counter",
            ]
        )
        for operation, value in sorted(lifecycle_conflicts.items()):
            lines.append(
                _sample("entry_lifecycle_conflicts_total", {"operation": operation}, value)
            )

        lines.extend(
            [
                "# HELP application_readiness Most recently observed readiness state.",
                "# TYPE application_readiness gauge",
                f"application_readiness {readiness}",
            ]
        )
        return "\n".join(lines) + "\n"


class MetricsMiddleware:
    """Measure each HTTP response exactly once without inspecting payloads."""

    def __init__(self, app: ASGIApp, registry: MetricsRegistry) -> None:
        self.app = app
        self.registry = registry

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") == METRICS_PATH:
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        response_status = 500

        async def capture_status(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
        finally:
            self.registry.observe_request(
                method=scope.get("method", "OTHER"),
                route=get_route_template(scope),
                status_code=response_status,
                duration_seconds=perf_counter() - started_at,
            )


def _bounded_method(method: str) -> str:
    normalized = method.upper()
    return (
        normalized
        if normalized in {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}
        else "OTHER"
    )


def _status_class(status_code: int) -> str:
    return f"{status_code // 100}xx" if 100 <= status_code <= 599 else "unknown"


def _http_labels(labels: tuple[str, str, str]) -> dict[str, str]:
    method, route, status_class = labels
    return {"method": method, "route": route, "status_class": status_class}


def _database_pool_values(database_pool: object | None) -> dict[str, int]:
    values = {"checked_in": 0, "checked_out": 0, "overflow": 0}
    if database_pool is None:
        return values
    for state, attribute in (
        ("checked_in", "checkedin"),
        ("checked_out", "checkedout"),
        ("overflow", "overflow"),
    ):
        value = getattr(database_pool, attribute, None)
        if callable(value):
            values[state] = max(0, int(value()))
    return values


def _sample(name: str, labels: dict[str, str], value: int | float) -> str:
    rendered_labels = ",".join(f'{key}="{_escape_label(label)}"' for key, label in labels.items())
    suffix = f"{{{rendered_labels}}}" if rendered_labels else ""
    return f"{name}{suffix} {_number(value)}"


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _number(value: int | float) -> str:
    return str(value) if isinstance(value, int) else format(value, ".15g")
