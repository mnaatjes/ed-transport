"""Abstract driven secondary SPI ports for network transport engine adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..base import DrivenPort
from ..dto.transport_dto import HttpRequestDTO, HttpResponseDTO


@runtime_checkable
class TransportEnginePort(DrivenPort, Protocol):
    """Synchronous driven SPI port for raw network transmission."""

    def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
        """Dispatches a request synchronously, returning the response."""
        ...

    def close(self) -> None:
        """Closes open network sockets and resources."""
        ...


@runtime_checkable
class AsyncTransportEnginePort(DrivenPort, Protocol):
    """Asynchronous driven SPI port for raw network transmission."""

    async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
        """Dispatches a request asynchronously, returning the response."""
        ...

    async def aclose(self) -> None:
        """Asynchronously closes open network sockets and resources."""
        ...
