"""Unit and fault injection tests for HTTP transport engines and SSE streaming."""

from __future__ import annotations

import httpx
import pytest

from ed_transport.adapters.driven.engine.httpx_engine import (
    HttpxAsyncEngineAdapter,
    HttpxSyncEngineAdapter,
)
from ed_transport.adapters.driven.stream.sse_stream import SseStreamEngineAdapter
from ed_transport.core.domain.exceptions import (
    TransportConnectionError,
    TransportError,
    TransportTimeoutError,
)
from ed_transport.core.ports.dto.transport_dto import HttpRequestDTO


class TestHttpxSyncEngineAdapter:
    """Verifies HttpxSyncEngineAdapter with MockTransport and fault injection."""

    def test_sync_send_success(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert str(request.url) == "https://api.eddn.io/v1/post"
            assert request.headers["x-custom"] == "test-header"
            assert request.content == b'{"status": "online"}'
            return httpx.Response(
                200, json={"ack": True}, headers={"content-type": "application/json"}
            )

        mock_client = httpx.Client(transport=httpx.MockTransport(handler))
        engine = HttpxSyncEngineAdapter(client=mock_client)

        req = HttpRequestDTO(
            url="https://api.eddn.io/v1/post",
            method="POST",
            headers={"x-custom": "test-header"},
            body=b'{"status": "online"}',
        )
        resp = engine.send(req)

        assert resp.status_code == 200
        assert resp.is_success is True
        assert b'"ack":true' in resp.body.lower()

    def test_sync_send_timeout_translation(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Socket timed out", request=request)

        mock_client = httpx.Client(transport=httpx.MockTransport(handler))
        engine = HttpxSyncEngineAdapter(client=mock_client)

        with pytest.raises(TransportTimeoutError) as exc_info:
            engine.send(HttpRequestDTO(url="https://api.eddn.io/timeout", timeout=5.0))

        assert exc_info.value.endpoint == "https://api.eddn.io/timeout"
        assert exc_info.value.timeout_seconds == 5.0
        assert isinstance(exc_info.value.__cause__, httpx.ReadTimeout)

    def test_sync_send_connection_error_translation(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Connection refused by peer", request=request)

        mock_client = httpx.Client(transport=httpx.MockTransport(handler))
        engine = HttpxSyncEngineAdapter(client=mock_client)

        with pytest.raises(TransportConnectionError) as exc_info:
            engine.send(HttpRequestDTO(url="https://api.eddn.io/refused"))

        assert "Connection refused" in exc_info.value.details
        assert isinstance(exc_info.value.__cause__, httpx.ConnectError)

    def test_sync_send_generic_http_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ProtocolError("Malformed response chunk", request=request)

        mock_client = httpx.Client(transport=httpx.MockTransport(handler))
        engine = HttpxSyncEngineAdapter(client=mock_client)

        with pytest.raises(TransportError) as exc_info:
            engine.send(HttpRequestDTO(url="https://api.eddn.io/protocol"))

        assert "Malformed response chunk" in str(exc_info.value)

    def test_sync_close_owned_client(self) -> None:
        engine = HttpxSyncEngineAdapter()
        assert engine._owns_client is True
        assert engine._client.is_closed is False
        engine.close()
        assert engine._client.is_closed is True


class TestHttpxAsyncEngineAdapter:
    """Verifies HttpxAsyncEngineAdapter with MockTransport and fault injection."""

    @pytest.mark.asyncio
    async def test_async_send_success(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert str(request.url) == "https://api.eddn.io/v1/status"
            return httpx.Response(200, text="System operational")

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        engine = HttpxAsyncEngineAdapter(client=mock_client)

        req = HttpRequestDTO(url="https://api.eddn.io/v1/status")
        resp = await engine.send_async(req)

        assert resp.status_code == 200
        assert resp.text == "System operational"

    @pytest.mark.asyncio
    async def test_async_send_timeout_translation(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectTimeout("Connect timeout", request=request)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        engine = HttpxAsyncEngineAdapter(client=mock_client)

        with pytest.raises(TransportTimeoutError) as exc_info:
            await engine.send_async(HttpRequestDTO(url="https://api.eddn.io/timeout", timeout=12.0))

        assert exc_info.value.endpoint == "https://api.eddn.io/timeout"
        assert exc_info.value.timeout_seconds == 12.0

    @pytest.mark.asyncio
    async def test_async_send_connection_error_translation(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.NetworkError("Network unreachable", request=request)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        engine = HttpxAsyncEngineAdapter(client=mock_client)

        with pytest.raises(TransportConnectionError) as exc_info:
            await engine.send_async(HttpRequestDTO(url="https://api.eddn.io/network-down"))

        assert "Network unreachable" in exc_info.value.details

    @pytest.mark.asyncio
    async def test_async_send_generic_http_error(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.DecodingError("Failed decoding gzip stream", request=request)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        engine = HttpxAsyncEngineAdapter(client=mock_client)

        with pytest.raises(TransportError) as exc_info:
            await engine.send_async(HttpRequestDTO(url="https://api.eddn.io/corrupt"))

        assert "Failed decoding gzip stream" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_async_close_owned_client(self) -> None:
        engine = HttpxAsyncEngineAdapter()
        assert engine._owns_client is True
        assert engine._client.is_closed is False
        await engine.aclose()
        assert engine._client.is_closed is True


class TestSseStreamEngineAdapter:
    """Verifies SSE streaming adapter parsing, comment skipping, and error handling."""

    @pytest.mark.asyncio
    async def test_sse_stream_multi_line_and_heartbeats(self) -> None:
        stream_content = (
            b": keep-alive heartbeat\n"
            b"event: telemetry\n"
            b"id: msg-101\n"
            b'data: {"commander":\n'
            b'data: "Jameson"}\n\n'
            b": another comment\n"
            b"data: second frame without event name\n\n"
            b"event: trailing\n"
            b"data: trailing data without ending newline"
        )

        async def handler(request: httpx.Request) -> httpx.Response:
            assert str(request.url).startswith("https://api.eddn.io/sse")
            assert request.headers["Accept"] == "text/event-stream"
            assert "topic=journal" in str(request.url)
            return httpx.Response(200, content=stream_content)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        engine = SseStreamEngineAdapter(client=mock_client)

        events = []
        async for evt in engine.open_stream("https://api.eddn.io/sse", topic="journal"):
            events.append(evt)

        assert len(events) == 3

        # Frame 1: multi-line data concatenation and id
        assert events[0].event_type == "telemetry"
        assert events[0].id == "msg-101"
        assert events[0].data == '{"commander":\n"Jameson"}'

        # Frame 2: default message type
        assert events[1].event_type == "message"
        assert events[1].id is None
        assert events[1].data == "second frame without event name"

        # Frame 3: trailing event
        assert events[2].event_type == "trailing"
        assert events[2].data == "trailing data without ending newline"

    @pytest.mark.asyncio
    async def test_sse_stream_non_200_raises_transport_error(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="Stream not found")

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        engine = SseStreamEngineAdapter(client=mock_client)

        with pytest.raises(TransportError, match="non-200 status: 404"):
            async for _ in engine.open_stream("https://api.eddn.io/sse/missing"):
                pass

    @pytest.mark.asyncio
    async def test_sse_stream_timeout_and_connection_errors(self) -> None:
        async def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("Stream read timeout", request=request)

        engine_timeout = SseStreamEngineAdapter(
            client=httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler))
        )
        with pytest.raises(TransportTimeoutError):
            async for _ in engine_timeout.open_stream("https://api.eddn.io/sse/timeout"):
                pass

        async def connect_err_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Stream connection refused", request=request)

        engine_connect = SseStreamEngineAdapter(
            client=httpx.AsyncClient(transport=httpx.MockTransport(connect_err_handler))
        )
        with pytest.raises(TransportConnectionError):
            async for _ in engine_connect.open_stream("https://api.eddn.io/sse/refused"):
                pass

    @pytest.mark.asyncio
    async def test_sse_stream_close_owned_client(self) -> None:
        engine = SseStreamEngineAdapter()
        assert engine._owns_client is True
        assert engine._client.is_closed is False
        await engine.aclose()
        assert engine._client.is_closed is True
