"""Comprehensive tests for domain models, value objects, and boundary DTOs."""

from __future__ import annotations

import pytest

from ed_transport.core.domain.exceptions import (
    DomainError,
    DomainValidationError,
    HealthCheckFailedError,
    InvalidPayloadTypeError,
    MaxRetriesExceededError,
    RateLimitExceededError,
    SpoolCapacityExceededError,
    SpoolStorageCorruptError,
    TransportConnectionError,
    TransportError,
    TransportTimeoutError,
)
from ed_transport.core.domain.models import (
    RateLimitConfig,
    RateLimitRule,
    RetryConfig,
    SpoolConfig,
)
from ed_transport.core.ports.dto.transport_dto import (
    HttpRequestDTO,
    HttpResponseDTO,
    RawStreamEventDTO,
    SpoolRecordDTO,
)


class TestDomainModelsValidation:
    """Verifies invariant validation on pure domain value objects."""

    def test_rate_limit_config_valid(self) -> None:
        cfg = RateLimitConfig(requests_per_second=10.0, burst_capacity=20, destination_key="eddn")
        assert cfg.requests_per_second == 10.0
        assert cfg.burst_capacity == 20
        assert cfg.destination_key == "eddn"

    def test_rate_limit_config_invalid_rates(self) -> None:
        with pytest.raises(DomainValidationError, match="requests_per_second must be positive"):
            RateLimitConfig(requests_per_second=0.0)

        with pytest.raises(DomainValidationError, match="requests_per_second must be positive"):
            RateLimitConfig(requests_per_second=-1.5)

        with pytest.raises(DomainValidationError, match="burst_capacity must be positive"):
            RateLimitConfig(burst_capacity=0)

        with pytest.raises(DomainValidationError, match="burst_capacity must be positive"):
            RateLimitConfig(burst_capacity=-5)

    def test_retry_config_valid(self) -> None:
        cfg = RetryConfig(max_retries=5, base_delay=1.0, max_backoff=15.0)
        assert cfg.max_retries == 5
        assert cfg.base_delay == 1.0
        assert cfg.max_backoff == 15.0
        assert 503 in cfg.retryable_statuses

    def test_retry_config_invalid(self) -> None:
        with pytest.raises(DomainValidationError, match="max_retries cannot be negative"):
            RetryConfig(max_retries=-1)

        with pytest.raises(DomainValidationError, match="base_delay must be positive"):
            RetryConfig(base_delay=0.0)

        with pytest.raises(DomainValidationError, match="base_delay must be positive"):
            RetryConfig(base_delay=-0.5)

        with pytest.raises(
            DomainValidationError, match="max_backoff cannot be less than base_delay"
        ):
            RetryConfig(base_delay=5.0, max_backoff=2.0)

    def test_rate_limit_rule_valid(self) -> None:
        rule = RateLimitRule(
            destination_pattern="api.eddn.io", requests_per_second=2.0, burst_capacity=4
        )
        assert rule.destination_pattern == "api.eddn.io"
        assert rule.requests_per_second == 2.0
        assert rule.burst_capacity == 4

    def test_rate_limit_rule_invalid(self) -> None:
        with pytest.raises(DomainValidationError, match="destination_pattern cannot be empty"):
            RateLimitRule(destination_pattern="")

        with pytest.raises(DomainValidationError, match="requests_per_second must be positive"):
            RateLimitRule(destination_pattern="eddn", requests_per_second=0)

        with pytest.raises(DomainValidationError, match="burst_capacity must be positive"):
            RateLimitRule(destination_pattern="eddn", burst_capacity=0)

    def test_spool_config_valid(self) -> None:
        cfg = SpoolConfig(
            max_capacity=500,
            memory_limit_bytes=1024,
            eviction_policy="RejectNewest",
            storage_path="/tmp/spool.db",
            auto_recover_corrupt=True,
        )
        assert cfg.max_capacity == 500
        assert cfg.memory_limit_bytes == 1024
        assert cfg.eviction_policy == "RejectNewest"
        assert cfg.storage_path == "/tmp/spool.db"
        assert cfg.auto_recover_corrupt is True

    def test_spool_config_invalid(self) -> None:
        with pytest.raises(DomainValidationError, match="max_capacity must be positive"):
            SpoolConfig(max_capacity=0)

        with pytest.raises(DomainValidationError, match="memory_limit_bytes must be positive"):
            SpoolConfig(memory_limit_bytes=0)

        with pytest.raises(DomainValidationError, match="Unsupported eviction policy"):
            SpoolConfig(eviction_policy="InvalidPolicy")


class TestTransportDTOValidation:
    """Verifies invariant validation on boundary DTOs."""

    def test_http_request_dto_valid(self) -> None:
        req = HttpRequestDTO(
            url="https://api.frontier.co.uk/profile",
            method="POST",
            headers={"Authorization": "Bearer token123"},
            body=b"payload",
            timeout=15.0,
        )
        assert req.url == "https://api.frontier.co.uk/profile"
        assert req.method == "POST"
        assert req.headers["Authorization"] == "Bearer token123"
        assert req.body == b"payload"
        assert req.timeout == 15.0

    def test_http_request_dto_invalid_url(self) -> None:
        with pytest.raises(DomainValidationError, match="Invalid request URL scheme"):
            HttpRequestDTO(url="")

        with pytest.raises(DomainValidationError, match="Invalid request URL scheme"):
            HttpRequestDTO(url="ftp://files.example.com")

        with pytest.raises(DomainValidationError, match="Invalid request URL scheme"):
            HttpRequestDTO(url="relative/path")

    def test_http_request_dto_invalid_method(self) -> None:
        with pytest.raises(DomainValidationError, match="Invalid or unsupported HTTP method"):
            HttpRequestDTO(url="https://api.example.com", method="INVALID")

    def test_http_request_dto_invalid_timeout(self) -> None:
        with pytest.raises(DomainValidationError, match="Request timeout must be positive"):
            HttpRequestDTO(url="https://api.example.com", timeout=0.0)

        with pytest.raises(DomainValidationError, match="Request timeout must be positive"):
            HttpRequestDTO(url="https://api.example.com", timeout=-1.0)

    def test_http_response_dto_valid(self) -> None:
        resp = HttpResponseDTO(
            status_code=200,
            headers={"Content-Type": "application/json"},
            body=b'{"commander": "Jameson"}',
        )
        assert resp.status_code == 200
        assert resp.is_success is True
        assert resp.text == '{"commander": "Jameson"}'

    def test_http_response_dto_non_success_and_invalid_status(self) -> None:
        resp = HttpResponseDTO(status_code=500, headers={}, body=b"Error")
        assert resp.is_success is False

        with pytest.raises(DomainValidationError, match="Invalid HTTP status code"):
            HttpResponseDTO(status_code=99, headers={}, body=b"")

        with pytest.raises(DomainValidationError, match="Invalid HTTP status code"):
            HttpResponseDTO(status_code=600, headers={}, body=b"")

    def test_stream_and_spool_dtos(self) -> None:
        stream_event = RawStreamEventDTO(
            event_type="telemetry",
            data='{"status": "docked"}',
            id="evt-1",
            retry=5000,
        )
        assert stream_event.event_type == "telemetry"
        assert stream_event.data == '{"status": "docked"}'
        assert stream_event.id == "evt-1"
        assert stream_event.retry == 5000

        req = HttpRequestDTO(url="https://api.example.com")
        spool_rec = SpoolRecordDTO(sequence_id=42, request=req, created_at=100.0, retry_count=2)
        assert spool_rec.sequence_id == 42
        assert spool_rec.request == req
        assert spool_rec.created_at == 100.0
        assert spool_rec.retry_count == 2


class TestDomainExceptions:
    """Verifies exception hierarchy, formatting, and causal properties."""

    def test_exception_inheritance_tree(self) -> None:
        assert issubclass(DomainValidationError, DomainError)
        assert issubclass(HealthCheckFailedError, DomainError)
        assert issubclass(TransportError, DomainError)
        assert issubclass(TransportTimeoutError, DomainError)
        assert issubclass(TransportConnectionError, DomainError)
        assert issubclass(RateLimitExceededError, DomainError)
        assert issubclass(MaxRetriesExceededError, DomainError)
        assert issubclass(SpoolCapacityExceededError, DomainError)
        assert issubclass(InvalidPayloadTypeError, DomainError)
        assert issubclass(SpoolStorageCorruptError, DomainError)

    def test_transport_timeout_error_attributes(self) -> None:
        err = TransportTimeoutError(
            endpoint="https://api.eddn.io", timeout_seconds=10.5, attempt_count=2
        )
        assert "timed out after 10.5s (attempt 2)" in str(err)
        assert err.endpoint == "https://api.eddn.io"
        assert err.timeout_seconds == 10.5
        assert err.attempt_count == 2

    def test_transport_connection_error_details(self) -> None:
        err_simple = TransportConnectionError(endpoint="https://api.eddn.io")
        assert str(err_simple) == "Connection to 'https://api.eddn.io' failed"

        err_detailed = TransportConnectionError(
            endpoint="https://api.eddn.io", details="ECONNREFUSED"
        )
        assert str(err_detailed) == "Connection to 'https://api.eddn.io' failed: ECONNREFUSED"
        assert err_detailed.details == "ECONNREFUSED"

    def test_rate_limit_exceeded_error(self) -> None:
        err = RateLimitExceededError(destination_key="capi", retry_after_seconds=3.14159)
        assert "Retry after 3.14s" in str(err)
        assert err.destination_key == "capi"
        assert err.retry_after_seconds == pytest.approx(3.14159)

    def test_max_retries_exceeded_error(self) -> None:
        cause = ValueError("Network dropped")
        err = MaxRetriesExceededError(
            endpoint="https://capi.elitedangerous.com", total_attempts=3, last_error=cause
        )
        assert "Exceeded maximum retries (3)" in str(err)
        assert "Network dropped" in str(err)
        assert err.last_error is cause

    def test_spool_capacity_and_payload_type_errors(self) -> None:
        cap_err = SpoolCapacityExceededError(current_depth=1000, capacity_ceiling=1000)
        assert "1000/1000 items" in str(cap_err)
        assert cap_err.current_depth == 1000

        payload_err = InvalidPayloadTypeError(dict)
        assert "must be bytes or str, not 'dict'" in str(payload_err)
        assert payload_err.invalid_type is dict

    def test_spool_storage_corrupt_error(self) -> None:
        corrupt_simple = SpoolStorageCorruptError(storage_path="/tmp/spool.db")
        assert "corrupted" in str(corrupt_simple)
        assert corrupt_simple.storage_path == "/tmp/spool.db"

        corrupt_detailed = SpoolStorageCorruptError(
            storage_path="/tmp/spool.db", details="bad magic header"
        )
        assert "bad magic header" in str(corrupt_detailed)
        assert corrupt_detailed.details == "bad magic header"
