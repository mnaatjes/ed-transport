"""Pure domain exception hierarchy for business rule violations."""

from __future__ import annotations


class DomainError(Exception):
    """Base domain exception. All domain errors must inherit from this root."""


class DomainValidationError(DomainError):
    """Raised when an entity or value object fails invariant self-validation."""


class HealthCheckFailedError(DomainError):
    """Raised when an assertive operational health check fails."""


class TransportError(DomainError):
    """Root exception for transport subsystem errors."""


class TransportTimeoutError(DomainError):
    """Raised when an HTTP or socket request times out."""

    def __init__(self, endpoint: str, timeout_seconds: float, attempt_count: int = 1) -> None:
        super().__init__(
            f"Request to '{endpoint}' timed out after {timeout_seconds}s (attempt {attempt_count})"
        )
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.attempt_count = attempt_count


class TransportConnectionError(DomainError):
    """Raised when socket connection fails or is reset."""

    def __init__(self, endpoint: str, details: str = "") -> None:
        msg = f"Connection to '{endpoint}' failed"
        if details:
            msg += f": {details}"
        super().__init__(msg)
        self.endpoint = endpoint
        self.details = details


class RateLimitExceededError(DomainError):
    """Raised when rate limit is exceeded in non-blocking mode or wait limit reached."""

    def __init__(self, destination_key: str, retry_after_seconds: float) -> None:
        super().__init__(
            f"Rate limit exceeded for destination '{destination_key}'. "
            f"Retry after {retry_after_seconds:.2f}s"
        )
        self.destination_key = destination_key
        self.retry_after_seconds = retry_after_seconds


class MaxRetriesExceededError(DomainError):
    """Raised when all retry attempts fail."""

    def __init__(
        self, endpoint: str, total_attempts: int, last_error: Exception | None = None
    ) -> None:
        msg = f"Exceeded maximum retries ({total_attempts}) for endpoint '{endpoint}'"
        if last_error:
            msg += f". Last error: {last_error}"
        super().__init__(msg)
        self.endpoint = endpoint
        self.total_attempts = total_attempts
        self.last_error = last_error


class SpoolCapacityExceededError(DomainError):
    """Raised when spool buffer capacity limit is reached under RejectNewest policy."""

    def __init__(self, current_depth: int, capacity_ceiling: int) -> None:
        super().__init__(
            f"Spool buffer capacity saturated: {current_depth}/{capacity_ceiling} items"
        )
        self.current_depth = current_depth
        self.capacity_ceiling = capacity_ceiling


class InvalidPayloadTypeError(DomainError):
    """Raised when body payload is not bytes or string (UC-04 domain agnosticism)."""

    def __init__(self, invalid_type: type) -> None:
        super().__init__(
            f"Payload body must be bytes or str, not '{invalid_type.__name__}'. "
            "Domain entities from ed-models must be serialized prior to dispatch."
        )
        self.invalid_type = invalid_type
