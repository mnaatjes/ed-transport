"""CLI driving adapter for health reporting."""

from __future__ import annotations

import json
from typing import Any

from ...core.ports.driving.health_port import GetHealthPort


class CliHealthAdapter:
    """Driving adapter executing health checks and formatting outputs for CLI runtimes.

    Architectural Role: Level 4 Concrete Driving Adapter.
    """

    def __init__(self, health_service: GetHealthPort) -> None:
        self._health_service = health_service

    def run(self) -> tuple[int, str]:
        """Executes health check and formats CLI response.

        Returns:
            A tuple of (exit_code, output_payload_json).
            Exit code 0 indicates healthy; 1 indicates degraded or unhealthy.
        """
        health = self._health_service.check_health()
        payload: dict[str, Any] = {
            "status": health.status,
            "service_name": health.service_name,
            "timestamp": health.timestamp.isoformat(),
        }
        exit_code = 0 if health.status == "healthy" else 1
        return exit_code, json.dumps(payload, indent=2)
