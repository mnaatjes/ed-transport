"""Health check use case orchestrating system probes."""

from __future__ import annotations

from ..domain.health import HealthStatus, SystemHealth
from ..ports.driven.probe_port import SystemProbePort
from ..ports.driving.health_port import GetHealthPort


class CheckHealthUseCase(GetHealthPort):
    """Interacts with driven probe ports to evaluate overall system health."""

    def __init__(self, probe: SystemProbePort, service_name: str) -> None:
        self._probe = probe
        self._service_name = service_name

    def check_health(self) -> SystemHealth:
        """Executes operational probe check and produces immutable SystemHealth DTO."""
        is_ok = self._probe.is_operational()
        status = HealthStatus.HEALTHY if is_ok else HealthStatus.UNHEALTHY
        return SystemHealth(
            status=status,
            service_name=self._service_name,
        )
