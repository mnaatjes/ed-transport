"""Pure domain exception hierarchy for business rule violations."""

from __future__ import annotations


class DomainError(Exception):
    """Base domain exception. All domain errors must inherit from this root."""


class DomainValidationError(DomainError):
    """Raised when an entity or value object fails invariant self-validation."""


class HealthCheckFailedError(DomainError):
    """Raised when an assertive operational health check fails."""
