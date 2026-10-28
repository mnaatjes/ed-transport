"""Pure domain models, entities, and value objects."""

from .exceptions import (
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
from .models import (
    RateLimitConfig,
    RateLimitRule,
    RetryConfig,
    SpoolConfig,
)

__all__ = (
    "DomainError",
    "DomainValidationError",
    "HealthCheckFailedError",
    "InvalidPayloadTypeError",
    "MaxRetriesExceededError",
    "RateLimitConfig",
    "RateLimitRule",
    "RateLimitExceededError",
    "RetryConfig",
    "SpoolCapacityExceededError",
    "SpoolConfig",
    "SpoolStorageCorruptError",
    "TransportConnectionError",
    "TransportError",
    "TransportTimeoutError",
)
