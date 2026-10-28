"""In-memory test doubles for driven secondary SPI ports."""

from __future__ import annotations

from collections import deque
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...src.ed_transport.core.ports.driven.engine_port import (
        AsyncTransportEnginePort,
        TransportEnginePort,
    )
    from ...src.ed_transport.core.ports.driven.rate_limiter_port import RateLimiterPort
    from ...src.ed_transport.core.ports.driven.spool_storage_port import SpoolStoragePort
    from ...src.ed_transport.core.ports.driven.stream_engine_port import StreamEnginePort
    from ...src.ed_transport.core.ports.dto.transport_dto import (
        HttpRequestDTO,
        HttpResponseDTO,
        RawStreamEventDTO,
        SpoolRecordDTO,
    )
else:
    AsyncTransportEnginePort = object
    RateLimiterPort = object
    SpoolStoragePort = object
    StreamEnginePort = object
    TransportEnginePort = object
    HttpRequestDTO = Any
    HttpResponseDTO = Any
    RawStreamEventDTO = Any
    SpoolRecordDTO = Any


class FakeTransportEngineAdapter(TransportEnginePort):
    """In-memory synchronous fake network transport adapter."""

    def __init__(self) -> None:
        self.sent_requests: list[HttpRequestDTO] = []
        self.responses: list[HttpResponseDTO] = []
        self.is_closed = False

    def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
        self.sent_requests.append(request)
        if self.responses:
            return self.responses.pop(0)
        from ed_transport.core.ports.dto.transport_dto import HttpResponseDTO

        return HttpResponseDTO(
            status_code=200,
            headers={"content-type": "application/json"},
            body=b"{}",
        )

    def close(self) -> None:
        self.is_closed = True


class FakeAsyncTransportEngineAdapter(AsyncTransportEnginePort):
    """In-memory asynchronous fake network transport adapter."""

    def __init__(self) -> None:
        self.sent_requests: list[HttpRequestDTO] = []
        self.responses: list[HttpResponseDTO] = []
        self.is_closed = False

    async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
        self.sent_requests.append(request)
        if self.responses:
            return self.responses.pop(0)
        from ed_transport.core.ports.dto.transport_dto import HttpResponseDTO

        return HttpResponseDTO(
            status_code=200,
            headers={"content-type": "application/json"},
            body=b"{}",
        )

    async def aclose(self) -> None:
        self.is_closed = True


class FakeRateLimiterAdapter(RateLimiterPort):
    """In-memory rate limiter test double with configurable grant behavior."""

    def __init__(self, should_grant: bool = True) -> None:
        self.should_grant = should_grant
        self.acquired_calls: list[str] = []

    def acquire(self, destination: str, timeout: float | None = None) -> bool:
        self.acquired_calls.append(destination)
        return self.should_grant

    async def acquire_async(self, destination: str, timeout: float | None = None) -> bool:
        self.acquired_calls.append(destination)
        return self.should_grant


class FakeSpoolStorageAdapter(SpoolStoragePort):
    """In-memory queue test double satisfying SpoolStoragePort."""

    def __init__(self) -> None:
        self._queue: deque[SpoolRecordDTO] = deque()
        self.is_closed = False

    def push(self, record: SpoolRecordDTO) -> None:
        self._queue.append(record)

    def pop(self) -> SpoolRecordDTO | None:
        if self._queue:
            return self._queue.popleft()
        return None

    def peek(self) -> SpoolRecordDTO | None:
        if self._queue:
            return self._queue[0]
        return None

    def count(self) -> int:
        return len(self._queue)

    def size_bytes(self) -> int:
        return sum(len(r.request.body or b"") for r in self._queue)

    def clear(self) -> None:
        self._queue.clear()

    def close(self) -> None:
        self.is_closed = True


class FakeStreamEngineAdapter(StreamEnginePort):
    """In-memory stream generator double satisfying StreamEnginePort."""

    def __init__(self) -> None:
        self.events_to_yield: list[RawStreamEventDTO] = []

    async def open_stream(
        self, endpoint: str, topic: str | None = None
    ) -> AsyncIterator[RawStreamEventDTO]:
        for event in self.events_to_yield:
            yield event
