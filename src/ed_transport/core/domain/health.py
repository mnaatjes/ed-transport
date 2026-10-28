"""Pure domain models for system health and status reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from .exceptions import DomainValidationError


class HealthStatus(StrEnum):
    """Canonical operational health statuses for the bounded context."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class SystemHealth:
    """Immutable domain representation of service health."""

    status: HealthStatus
    service_name: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        """Enforces domain entity invariants."""
        if not self.service_name or not self.service_name.strip():
            raise DomainValidationError("service_name cannot be empty or blank")
