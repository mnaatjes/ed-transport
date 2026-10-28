"""Abstract driven secondary SPI port for offline spool storage persistence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..base import DrivenPort
from ..dto.transport_dto import SpoolRecordDTO


@runtime_checkable
class SpoolStoragePort(DrivenPort, Protocol):
    """Secondary driven SPI port for persistent offline request queue storage."""

    def push(self, record: SpoolRecordDTO) -> None:
        """Appends a record to the bounded spool storage."""
        ...

    def pop(self) -> SpoolRecordDTO | None:
        """Removes and returns the oldest record from the queue in FIFO order."""
        ...

    def peek(self) -> SpoolRecordDTO | None:
        """Returns the oldest record without dequeuing it."""
        ...

    def count(self) -> int:
        """Returns the total number of enqueued records."""
        ...

    def size_bytes(self) -> int:
        """Returns the aggregate byte size consumed by stored requests."""
        ...

    def clear(self) -> None:
        """Deletes all enqueued records from storage."""
        ...

    def close(self) -> None:
        """Releases underlying database connections, handles, and file locks."""
        ...
