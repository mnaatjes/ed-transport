from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...src.core.domain.health import HealthStatus, SystemHealth
    from ...src.core.ports.driven.probe_port import SystemProbePort
else:
    HealthStatus = Any
    SystemHealth = Any
    SystemProbePort = object


class FakeSystemProbeAdapter(SystemProbePort):
    """In-memory test double for SystemProbePort.

    Enables testing application use cases completely offline without invoking OS APIs.
    """

    def __init__(self, default_status: HealthStatus = "healthy") -> None:
        self._status = default_status
        self._details: dict[str, Any] = {"mode": "in_memory_fake"}
        self._failure_mode = False

    def probe_system(self, service_name: str) -> SystemHealth:
        """Returns simulated in-memory system health."""
        if self._failure_mode:
            return SystemHealth(
                status="unhealthy",
                service_name=service_name,
            )
        return SystemHealth(
            status=self._status,
            service_name=service_name,
        )

    def set_failure_mode(self, should_fail: bool) -> None:
        """Configurable fault injection for testing negative branch scenarios."""
        self._failure_mode = should_fail

    def set_status(self, status: HealthStatus) -> None:
        """Sets simulated health status."""
        self._status = status

    def reset(self) -> None:
        """Resets simulated in-memory state."""
        self._status = "healthy"
        self._details = {"mode": "in_memory_fake"}
        self._failure_mode = False
