"""Composition root wiring adapters and interactors into executable runtime services."""

from __future__ import annotations

from ..adapters.driven.system_probe import OsSystemProbeAdapter
from ..adapters.driving.cli_health import CliHealthAdapter
from ..core.ports.driven.probe_port import SystemProbePort
from ..core.ports.driving.health_port import GetHealthPort
from ..core.use_cases.check_health import CheckHealthUseCase


class Container:
    """Dependency injection container and composition root.

    Wires concrete adapters to use cases and enforces interface contracts.
    """

    def __init__(self, service_name: str = "health-service") -> None:
        self.service_name = service_name

    def build_system_probe(self) -> SystemProbePort:
        """Instantiates concrete driven adapter."""
        adapter = OsSystemProbeAdapter()
        assert isinstance(adapter, SystemProbePort), "Adapter must satisfy SystemProbePort"
        return adapter

    def build_health_use_case(self) -> GetHealthPort:
        """Instantiates use case interactor with injected driven adapter."""
        probe = self.build_system_probe()
        use_case = CheckHealthUseCase(probe=probe, service_name=self.service_name)
        assert isinstance(use_case, GetHealthPort), "Use case must satisfy GetHealthPort"
        return use_case

    def build_cli_health_adapter(self) -> CliHealthAdapter:
        """Instantiates driving adapter with injected use case."""
        use_case = self.build_health_use_case()
        return CliHealthAdapter(health_service=use_case)
