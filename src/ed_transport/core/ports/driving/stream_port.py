"""Driving (inbound / primary) port contracts for telemetry streaming and IPC."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ..base import DrivingPort
from ..dto import RawStreamEventDTO


@runtime_checkable
class TelemetryStreamPort(DrivingPort, Protocol):
    """Primary port for subscribing to live telemetry streams over SSE."""

    def open_stream(
        self, endpoint: str = "/api/v1/stream", topic: str | None = None
    ) -> AsyncIterator[RawStreamEventDTO]:
        """Opens persistent stream and yields raw parsed event frames."""
        ...

    @property
    def is_alive(self) -> bool:
        """Returns True if the underlying stream connection is healthy."""
        ...
