"""Root marker protocols for Hexagonal Architecture ports."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Port(Protocol):
    """Universal root marker protocol for all hexagonal boundary ports."""


@runtime_checkable
class DrivingPort(Port, Protocol):
    """Inbound / Primary port protocol implemented by use cases or core services."""


@runtime_checkable
class DrivenPort(Port, Protocol):
    """Outbound / Secondary port protocol implemented by external adapters."""


@runtime_checkable
class DataTransferObject(Protocol):
    """Universal marker protocol for immutable boundary Data Transfer Objects."""
