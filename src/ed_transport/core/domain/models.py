"""Pure domain configuration value objects."""

from __future__ import annotations

from dataclasses import dataclass

from .exceptions import DomainValidationError


@dataclass(frozen=True)
class RateLimitConfig:
    """Configuration for destination rate-limiting."""

    requests_per_second: float = 5.0
    burst_capacity: int = 10
    destination_key: str = "default"

    def __post_init__(self) -> None:
        """Validates rate limit configuration."""
        if self.requests_per_second <= 0:
            raise DomainValidationError("requests_per_second must be positive")
        if self.burst_capacity <= 0:
            raise DomainValidationError("burst_capacity must be positive")


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for exponential backoff and jitter retry loops."""

    max_retries: int = 3
    base_delay: float = 0.5
    max_backoff: float = 10.0
    retryable_statuses: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})

    def __post_init__(self) -> None:
        """Validates retry configuration."""
        if self.max_retries < 0:
            raise DomainValidationError("max_retries cannot be negative")
        if self.base_delay <= 0:
            raise DomainValidationError("base_delay must be positive")
        if self.max_backoff < self.base_delay:
            raise DomainValidationError("max_backoff cannot be less than base_delay")


@dataclass(frozen=True)
class RateLimitRule:
    """Rate limit rule for destination matching."""

    destination_pattern: str
    requests_per_second: float = 5.0
    burst_capacity: int = 10

    def __post_init__(self) -> None:
        """Validates rate limit rule parameters."""
        if not self.destination_pattern:
            raise DomainValidationError("destination_pattern cannot be empty")
        if self.requests_per_second <= 0:
            raise DomainValidationError("requests_per_second must be positive")
        if self.burst_capacity <= 0:
            raise DomainValidationError("burst_capacity must be positive")


@dataclass(frozen=True)
class SpoolConfig:
    """Configuration for bounded circular spool buffer."""

    max_capacity: int = 1000
    memory_limit_bytes: int = 10 * 1024 * 1024  # 10 MB default
    eviction_policy: str = "DropOldest"
    storage_path: str = ""  # Empty = in-memory buffer
    auto_recover_corrupt: bool = False  # If True, re-creates corrupt db

    def __post_init__(self) -> None:
        """Validates spool configuration."""
        if self.max_capacity <= 0:
            raise DomainValidationError("max_capacity must be positive")
        if self.memory_limit_bytes <= 0:
            raise DomainValidationError("memory_limit_bytes must be positive")
        if self.eviction_policy not in {"DropOldest", "RejectNewest"}:
            raise DomainValidationError(f"Unsupported eviction policy: '{self.eviction_policy}'")
