"""Unit tests for TransportClient and AsyncTransportClient driving facades."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from ed_transport.adapters.driving.client import AsyncTransportClient, TransportClient
from ed_transport.core.domain.exceptions import InvalidPayloadTypeError
from ed_transport.core.ports.driving.spool_port import SpoolManagerPort
from ed_transport.core.ports.driving.stream_port import TelemetryStreamPort
from ed_transport.core.ports.driving.transport_port import (
    AsyncTransportPort,
    TransportPort,
)
from ed_transport.core.ports.dto import HttpRequestDTO, HttpResponseDTO, RawStreamEventDTO


class DummySyncTransportPort(TransportPort):
    def __init__(self, status_code: int = 200, body: bytes = b'{"status": "ok"}') -> None:
        self.status_code = status_code
        self.body = body
        self.last_request: HttpRequestDTO | None = None

    def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
        self.last_request = request
        if self.status_code >= 500:
            raise ConnectionResetError("Connection reset by peer")
        return HttpResponseDTO(status_code=self.status_code, headers={}, body=self.body)


class DummyAsyncTransportPort(AsyncTransportPort):
    def __init__(self, status_code: int = 200, body: bytes = b'{"status": "ok"}') -> None:
        self.status_code = status_code
        self.body = body
        self.last_request: HttpRequestDTO | None = None

    async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
        self.last_request = request
        if self.status_code >= 500:
            raise ConnectionResetError("Connection reset by peer")
        return HttpResponseDTO(status_code=self.status_code, headers={}, body=self.body)


class DummySpoolPort(SpoolManagerPort):
    def __init__(self) -> None:
        self.queue: list[HttpRequestDTO] = []

    def enqueue(self, request: HttpRequestDTO) -> bool:
        self.queue.append(request)
        return True

    def drain(self, batch_size: int = 50) -> int:
        count = min(batch_size, len(self.queue))
        self.queue = self.queue[count:]
        return count

    @property
    def depth(self) -> int:
        return len(self.queue)


class DummyStreamPort(TelemetryStreamPort):
    def __init__(self, events: list[RawStreamEventDTO] | None = None) -> None:
        self.events = events or [RawStreamEventDTO(event_type="test", data='{"foo": "bar"}')]
        self._alive = True

    async def open_stream(
        self, endpoint: str = "/api/v1/stream", topic: str | None = None
    ) -> AsyncIterator[RawStreamEventDTO]:
        for event in self.events:
            yield event

    @property
    def is_alive(self) -> bool:
        return self._alive


# -------------------------------------------------------------------------
# Synchronous Facade Tests (TransportClient)
# -------------------------------------------------------------------------


def test_sync_client_get_dispatches_proper_dto() -> None:
    port = DummySyncTransportPort()
    client = TransportClient(transport_port=port)

    response = client.get(
        "https://inara.cz/api/v2",
        headers={"Accept": "application/json"},
        params={"q": "1"},
    )

    assert response.status_code == 200
    assert response.is_success is True
    assert port.last_request is not None
    assert port.last_request.method == "GET"
    assert "https://inara.cz/api/v2?q=1" in port.last_request.url
    assert port.last_request.headers["Accept"] == "application/json"


def test_sync_client_post_serializes_str_body_to_bytes() -> None:
    port = DummySyncTransportPort()
    client = TransportClient(transport_port=port)

    response = client.post("https://eddn.edcd.io/upload/", body='{"schema": "test"}')

    assert response.status_code == 200
    assert port.last_request is not None
    assert port.last_request.method == "POST"
    assert port.last_request.body == b'{"schema": "test"}'


def test_sync_client_post_preserves_raw_bytes() -> None:
    port = DummySyncTransportPort()
    client = TransportClient(transport_port=port)
    raw_payload = b"\x01\x02\x03\x04"

    response = client.post("https://eddn.edcd.io/upload/", body=raw_payload)

    assert response.status_code == 200
    assert port.last_request is not None
    assert port.last_request.body == raw_payload


def test_sync_client_put_and_delete_verbs() -> None:
    port = DummySyncTransportPort()
    client = TransportClient(transport_port=port)

    client.put("https://example.com/api", body=b"data")
    assert port.last_request is not None
    assert port.last_request.method == "PUT"

    client.delete("https://example.com/api/1")
    assert port.last_request is not None
    assert port.last_request.method == "DELETE"


def test_sync_client_rejects_arbitrary_objects_as_body() -> None:
    port = DummySyncTransportPort()
    client = TransportClient(transport_port=port)

    with pytest.raises(InvalidPayloadTypeError) as exc_info:
        client.post("https://example.com", body={"key": "val"})  # type: ignore[arg-type]

    assert "dict" in str(exc_info.value)


def test_sync_client_context_manager_lifecycle() -> None:
    with TransportClient() as client:
        assert client.is_closed is False
    assert client.is_closed is True


def test_sync_client_send_buffered_enqueues_on_network_down() -> None:
    port = DummySyncTransportPort(status_code=500)
    spool = DummySpoolPort()
    client = TransportClient(transport_port=port, spool_port=spool)

    buffered = client.send_buffered(url="https://eddn.edcd.io/upload/", body=b"data")

    assert buffered is True
    assert client.spool_depth == 1
    assert spool.depth == 1

    drained = client.drain_spool()
    assert drained == 1
    assert client.spool_depth == 0


# -------------------------------------------------------------------------
# Asynchronous Facade Tests (AsyncTransportClient)
# -------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_async_client_get_dispatches_proper_dto() -> None:
    port = DummyAsyncTransportPort()
    client = AsyncTransportClient(transport_port=port)

    response = await client.get_async(
        "https://inara.cz/api/v2",
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert port.last_request is not None
    assert port.last_request.method == "GET"
    assert port.last_request.url == "https://inara.cz/api/v2"


@pytest.mark.asyncio
async def test_async_client_post_serializes_and_preserves_bytes() -> None:
    port = DummyAsyncTransportPort()
    client = AsyncTransportClient(transport_port=port)

    await client.post_async("https://inara.cz/api/v2", body='{"test": 1}')
    assert port.last_request is not None
    assert port.last_request.body == b'{"test": 1}'

    await client.post_async("https://inara.cz/api/v2", body=b"raw-bytes")
    assert port.last_request is not None
    assert port.last_request.body == b"raw-bytes"


@pytest.mark.asyncio
async def test_async_client_put_and_delete_verbs() -> None:
    port = DummyAsyncTransportPort()
    client = AsyncTransportClient(transport_port=port)

    await client.put_async("https://example.com/api", body=b"put-data")
    assert port.last_request is not None
    assert port.last_request.method == "PUT"

    await client.delete_async("https://example.com/api/2")
    assert port.last_request is not None
    assert port.last_request.method == "DELETE"


@pytest.mark.asyncio
async def test_async_client_rejects_arbitrary_objects_as_body() -> None:
    port = DummyAsyncTransportPort()
    client = AsyncTransportClient(transport_port=port)

    with pytest.raises(InvalidPayloadTypeError):
        await client.post_async("https://example.com", body=[1, 2, 3])  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_async_client_context_manager_lifecycle() -> None:
    async with AsyncTransportClient() as client:
        assert client.is_closed is False
    assert client.is_closed is True


@pytest.mark.asyncio
async def test_async_client_send_buffered_enqueues_on_network_down() -> None:
    port = DummyAsyncTransportPort(status_code=503)
    spool = DummySpoolPort()
    client = AsyncTransportClient(transport_port=port, spool_port=spool)

    buffered = await client.send_buffered_async(url="https://eddn.edcd.io/upload/", body=b"data")

    assert buffered is True
    assert client.spool_depth == 1

    drained = await client.drain_spool_async()
    assert drained == 1
    assert client.spool_depth == 0


@pytest.mark.asyncio
async def test_async_client_open_stream_yields_events() -> None:
    stream = DummyStreamPort()
    client = AsyncTransportClient(stream_port=stream)

    assert client.is_stream_alive is True

    received: list[RawStreamEventDTO] = []
    async for event in client.open_stream():
        received.append(event)

    assert len(received) == 1
    assert received[0].event_type == "test"
    assert received[0].data == '{"foo": "bar"}'
