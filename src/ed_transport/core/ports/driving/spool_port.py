"""Driving (inbound / primary) port contracts for offline request spooling."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..base import DrivingPort
from ..dto import HttpRequestDTO


@runtime_checkable
class SpoolManagerPort(DrivingPort, Protocol):
    """Primary port for managing offline request spooling and draining."""

    def enqueue(self, request: HttpRequestDTO) -> bool:
        """Enqueues an outbound request into the bounded spool buffer."""
        ...

    def drain(self, batch_size: int = 50) -> int:
        """Drains enqueued requests and dispatches them in FIFO order."""
        ...

    @property
    def depth(self) -> int:
        """Returns the number of currently enqueued requests."""
        ...
