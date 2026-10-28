"""Driving (inbound / primary) port contracts for HTTP transport."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..base import DrivingPort
from ..dto import HttpRequestDTO, HttpResponseDTO


@runtime_checkable
class TransportPort(DrivingPort, Protocol):
    """Synchronous primary port for dispatching resilient network requests."""

    def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
        """Executes resilient network dispatch honoring rate limits and retries."""
        ...


@runtime_checkable
class AsyncTransportPort(DrivingPort, Protocol):
    """Asynchronous primary port for dispatching resilient network requests."""

    async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
        """Asynchronously executes resilient network dispatch."""
        ...
