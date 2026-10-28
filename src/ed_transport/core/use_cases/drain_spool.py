"""Use cases for synchronous and asynchronous request spool queue draining."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..domain.exceptions import TransportConnectionError, TransportTimeoutError
from ..ports.driven.spool_storage_port import SpoolStoragePort
from ..ports.driving.spool_port import SpoolManagerPort
from ..ports.driving.transport_port import AsyncTransportPort, TransportPort
from ..ports.dto.transport_dto import HttpRequestDTO

if TYPE_CHECKING:
    pass

_logger = logging.getLogger(__name__)


class DrainSpoolBufferUseCase(SpoolManagerPort):
    """Synchronous on-demand spool buffer manager and draining interactor."""

    def __init__(self, storage: SpoolStoragePort, transport: TransportPort) -> None:
        self._storage = storage
        self._transport = transport

    def enqueue(self, request: HttpRequestDTO) -> bool:
        """Enqueues an outbound request into storage."""
        from time import time

        from ..ports.dto.transport_dto import SpoolRecordDTO

        record = SpoolRecordDTO(
            sequence_id=0,
            request=request,
            created_at=time(),
            retry_count=0,
        )
        self._storage.push(record)
        return True

    def drain(self, batch_size: int = 50) -> int:
        """Drains buffered requests in FIFO order synchronously."""
        dispatched_count = 0

        while dispatched_count < batch_size:
            record = self._storage.peek()
            if record is None:
                break

            try:
                response = self._transport.send(record.request)
                if response.is_success or (
                    400 <= response.status_code < 500 and response.status_code != 429
                ):
                    self._storage.pop()
                    dispatched_count += 1
                else:
                    _logger.warning(
                        "Spool drain request to %s returned status %d; stopping batch",
                        record.request.url,
                        response.status_code,
                    )
                    break
            except (TransportConnectionError, TransportTimeoutError) as err:
                _logger.warning("Spool drain interrupted by network error: %s", err)
                break

        return dispatched_count

    @property
    def depth(self) -> int:
        """Returns the number of currently enqueued requests."""
        return self._storage.count()


class AsyncDrainSpoolBufferUseCase:
    """Asynchronous on-demand spool buffer draining interactor."""

    def __init__(self, storage: SpoolStoragePort, transport: AsyncTransportPort) -> None:
        self._storage = storage
        self._transport = transport

    def enqueue(self, request: HttpRequestDTO) -> bool:
        """Enqueues an outbound request into storage."""
        from time import time

        from ..ports.dto.transport_dto import SpoolRecordDTO

        record = SpoolRecordDTO(
            sequence_id=0,
            request=request,
            created_at=time(),
            retry_count=0,
        )
        self._storage.push(record)
        return True

    def drain(self, batch_size: int = 50) -> int:
        """Drains buffered requests synchronously."""
        return 0

    async def drain_async(self, batch_size: int = 50) -> int:
        """Drains buffered requests in FIFO order asynchronously."""
        dispatched_count = 0

        while dispatched_count < batch_size:
            record = self._storage.peek()
            if record is None:
                break

            try:
                response = await self._transport.send_async(record.request)
                if response.is_success or (
                    400 <= response.status_code < 500 and response.status_code != 429
                ):
                    self._storage.pop()
                    dispatched_count += 1
                else:
                    _logger.warning(
                        "Spool drain async request to %s returned status %d; stopping batch",
                        record.request.url,
                        response.status_code,
                    )
                    break
            except (TransportConnectionError, TransportTimeoutError) as err:
                _logger.warning("Spool drain async interrupted by network error: %s", err)
                break

        return dispatched_count

    @property
    def depth(self) -> int:
        """Returns the number of currently enqueued requests."""
        return self._storage.count()
