"""Fast in-memory spool storage adapter using collections.deque."""

from __future__ import annotations

import threading
from collections import deque

from ....core.domain.exceptions import SpoolCapacityExceededError
from ....core.ports.driven.spool_storage_port import SpoolStoragePort
from ....core.ports.dto.transport_dto import SpoolRecordDTO


class MemorySpoolStorageAdapter(SpoolStoragePort):
    """In-memory circular FIFO spool buffer."""

    def __init__(
        self,
        max_capacity: int = 1000,
        memory_limit_bytes: int = 10 * 1024 * 1024,
        eviction_policy: str = "DropOldest",
    ) -> None:
        self._max_capacity = max_capacity
        self._memory_limit_bytes = memory_limit_bytes
        self._eviction_policy = eviction_policy
        self._queue: deque[SpoolRecordDTO] = deque()
        self._current_bytes = 0
        self._lock = threading.RLock()
        self._seq = 0

    def push(self, record: SpoolRecordDTO) -> None:
        """Pushes a record into memory buffer, enforcing capacity and eviction rules."""
        with self._lock:
            body_size = len(record.request.body or b"")
            if len(self._queue) >= self._max_capacity or (
                self._current_bytes + body_size > self._memory_limit_bytes
            ):
                if self._eviction_policy == "RejectNewest":
                    raise SpoolCapacityExceededError(
                        current_depth=len(self._queue),
                        capacity_ceiling=self._max_capacity,
                    )
                # Drop oldest
                while self._queue and (
                    len(self._queue) >= self._max_capacity
                    or (self._current_bytes + body_size > self._memory_limit_bytes)
                ):
                    oldest = self._queue.popleft()
                    self._current_bytes -= len(oldest.request.body or b"")

            self._seq += 1
            stamped = SpoolRecordDTO(
                sequence_id=self._seq,
                request=record.request,
                created_at=record.created_at,
                retry_count=record.retry_count,
            )
            self._queue.append(stamped)
            self._current_bytes += body_size

    def pop(self) -> SpoolRecordDTO | None:
        """Pops the oldest record from the queue."""
        with self._lock:
            if not self._queue:
                return None
            record = self._queue.popleft()
            self._current_bytes -= len(record.request.body or b"")
            return record

    def peek(self) -> SpoolRecordDTO | None:
        """Peeks at the oldest record in the queue without removing it."""
        with self._lock:
            if not self._queue:
                return None
            return self._queue[0]

    def count(self) -> int:
        """Returns the number of enqueued records."""
        with self._lock:
            return len(self._queue)

    def size_bytes(self) -> int:
        """Returns aggregate bytes held in memory."""
        with self._lock:
            return self._current_bytes

    def clear(self) -> None:
        """Clears all records from buffer."""
        with self._lock:
            self._queue.clear()
            self._current_bytes = 0

    def close(self) -> None:
        """Releases resources."""
        self.clear()
