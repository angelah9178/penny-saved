"""Tests for the stable production operations contracts."""

from app.core.operations import (
    FORBIDDEN_OBSERVABILITY_VALUES,
    LIVENESS_CONTRACT,
    METRIC_CONTRACTS,
    METRICS_PATH,
    READINESS_CONTRACT,
    REQUEST_ID_FORMAT,
    REQUEST_ID_HEADER,
    REQUEST_ID_MAX_LENGTH,
    STRUCTURED_LOG_OPTIONAL_FIELDS,
    STRUCTURED_LOG_REQUIRED_FIELDS,
    UNMATCHED_ROUTE_TEMPLATE,
)


def test_structured_log_contract_has_stable_safe_fields() -> None:
    assert {
        "timestamp",
        "level",
        "environment",
        "event",
        "request_id",
        "method",
        "route",
        "status",
        "duration_ms",
    } == STRUCTURED_LOG_REQUIRED_FIELDS
    assert {"user_id", "context"} == STRUCTURED_LOG_OPTIONAL_FIELDS
    assert not (
        (STRUCTURED_LOG_REQUIRED_FIELDS | STRUCTURED_LOG_OPTIONAL_FIELDS)
        & FORBIDDEN_OBSERVABILITY_VALUES
    )
    assert UNMATCHED_ROUTE_TEMPLATE == "unmatched"


def test_request_correlation_contract_is_bounded() -> None:
    assert REQUEST_ID_HEADER == "X-Request-ID"
    assert REQUEST_ID_FORMAT == "canonical UUID"
    assert REQUEST_ID_MAX_LENGTH == 36


def test_metric_contract_names_and_labels_are_unique_and_bounded() -> None:
    names = [contract.name for contract in METRIC_CONTRACTS]

    assert len(names) == len(set(names))
    assert {"requests", "seconds", "errors", "connections", "failures", "conflicts", "state"} == {
        contract.unit for contract in METRIC_CONTRACTS
    }
    for contract in METRIC_CONTRACTS:
        assert len(contract.labels) == len(set(contract.labels))
        assert not set(contract.labels) & FORBIDDEN_OBSERVABILITY_VALUES
        assert contract.purpose
    assert METRICS_PATH == "/internal/metrics"


def test_health_contract_separates_liveness_from_readiness() -> None:
    assert LIVENESS_CONTRACT.path == "/api/health"
    assert LIVENESS_CONTRACT.success_status == 200
    assert LIVENESS_CONTRACT.failure_status is None
    assert LIVENESS_CONTRACT.depends_on_database is False
    assert dict(LIVENESS_CONTRACT.success_body) == {"status": "ok"}

    assert READINESS_CONTRACT.path == "/api/ready"
    assert READINESS_CONTRACT.success_status == 200
    assert READINESS_CONTRACT.failure_status == 503
    assert READINESS_CONTRACT.depends_on_database is True
    assert dict(READINESS_CONTRACT.success_body) == {"status": "ready"}
    assert dict(READINESS_CONTRACT.failure_body or ()) == {"status": "unavailable"}
