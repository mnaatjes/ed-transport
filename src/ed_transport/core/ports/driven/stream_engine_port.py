"""Abstract driven secondary SPI port for telemetry stream network adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ..base import DrivenPort
from ..dto.transport_dto import RawStreamEventDTO


@runtime_checkable
class StreamEnginePort(DrivenPort, Protocol):
    """Secondary driven SPI port for establishing chunked event stream connections."""

    def open_stream(
        self, endpoint: str, topic: str | None = None
    ) -> AsyncIterator[RawStreamEventDTO]:
        """Opens persistent stream and yields raw decoded stream frames."""
        ...
