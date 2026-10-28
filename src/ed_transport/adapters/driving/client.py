"""Driving adapter facades (TransportClient, AsyncTransportClient) for ed-transport."""

from __future__ import annotations

import types
from collections.abc import AsyncIterator, Mapping

from ...core.domain.exceptions import InvalidPayloadTypeError
from ...core.domain.models import (
    RateLimitConfig,
    RetryConfig,
    SpoolConfig,
)
from ...core.ports.driving.spool_port import SpoolManagerPort
from ...core.ports.driving.stream_port import TelemetryStreamPort
from ...core.ports.driving.transport_port import (
    AsyncTransportPort,
    TransportPort,
)
from ...core.ports.dto import HttpRequestDTO, HttpResponseDTO, RawStreamEventDTO


class TransportClient:
    """Synchronous driving adapter facade for ed-transport.

    Provides high-level, ergonomic methods for HTTP requests, bounded offline spooling,
    and credential injection, delegating strictly to driving ports.
    """

    def __init__(
        self,
        transport_port: TransportPort | None = None,
        spool_port: SpoolManagerPort | None = None,
        rate_limit_config: RateLimitConfig | None = None,
        retry_config: RetryConfig | None = None,
        spool_config: SpoolConfig | None = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._transport_port = transport_port
        self._spool_port = spool_port
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self.retry_config = retry_config or RetryConfig()
        self.spool_config = spool_config or SpoolConfig()
        self.default_timeout = default_timeout
        self._is_closed = False

    def __enter__(self) -> TransportClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Closes client resources."""
        self._is_closed = True

    @property
    def is_closed(self) -> bool:
        """Returns True if the client is closed."""
        return self._is_closed

    @property
    def spool_depth(self) -> int:
        """Returns the number of currently spooled requests."""
        if self._spool_port is None:
            return 0
        return self._spool_port.depth

    def _normalize_body(self, body: bytes | str | None) -> bytes:
        """Validates and normalizes payload body into raw bytes."""
        if body is None:
            return b""
        if isinstance(body, bytes):
            return body
        if isinstance(body, str):
            return body.encode("utf-8")
        raise InvalidPayloadTypeError(type(body))

    def _build_request(
        self,
        url: str,
        method: str,
        body: bytes | str | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpRequestDTO:
        """Constructs an immutable HttpRequestDTO."""
        norm_body = self._normalize_body(body)
        hdrs: dict[str, str] = dict(headers) if headers else {}
        target_url = url
        if params:
            import urllib.parse

            query_string = urllib.parse.urlencode(params)
            sep = "&" if "?" in target_url else "?"
            target_url = f"{target_url}{sep}{query_string}"

        return HttpRequestDTO(
            url=target_url,
            method=method.upper(),
            headers=hdrs,
            body=norm_body,
            timeout=timeout if timeout is not None else self.default_timeout,
        )

    def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
        """Dispatches an immutable HttpRequestDTO."""
        if self._transport_port is None:
            raise RuntimeError("HttpTransportPort is not configured on this client")
        return self._transport_port.send(request)

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponseDTO:
        """Dispatches an HTTP GET request."""
        req = self._build_request(url, "GET", None, headers, params, timeout)
        return self.send(req)

    def post(
        self,
        url: str,
        *,
        body: bytes | str | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponseDTO:
        """Dispatches an HTTP POST request."""
        req = self._build_request(url, "POST", body, headers, params, timeout)
        return self.send(req)

    def put(
        self,
        url: str,
        *,
        body: bytes | str | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponseDTO:
        """Dispatches an HTTP PUT request."""
        req = self._build_request(url, "PUT", body, headers, params, timeout)
        return self.send(req)

    def delete(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponseDTO:
        """Dispatches an HTTP DELETE request."""
        req = self._build_request(url, "DELETE", None, headers, params, timeout)
        return self.send(req)

    def send_buffered(
        self,
        request: HttpRequestDTO | None = None,
        *,
        url: str | None = None,
        method: str = "POST",
        body: bytes | str | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> bool:
        """Sends immediately or buffers to offline spool if network is unreachable."""
        req = request or self._build_request(url or "", method, body, headers, params, timeout)
        try:
            res = self.send(req)
            return res.is_success
        except Exception:
            if self._spool_port is not None:
                return self._spool_port.enqueue(req)
            raise

    def drain_spool(self, batch_size: int = 50) -> int:
        """Drains enqueued requests and dispatches in FIFO order."""
        if self._spool_port is None:
            return 0
        return self._spool_port.drain(batch_size)


class AsyncTransportClient:
    """Asynchronous driving adapter facade for ed-transport.

    Native async/await interface for reactive event loops and streaming applications.
    """

    def __init__(
        self,
        transport_port: AsyncTransportPort | None = None,
        spool_port: SpoolManagerPort | None = None,
        stream_port: TelemetryStreamPort | None = None,
        rate_limit_config: RateLimitConfig | None = None,
        retry_config: RetryConfig | None = None,
        spool_config: SpoolConfig | None = None,
        default_timeout: float = 30.0,
    ) -> None:
        self._transport_port = transport_port

        self._spool_port = spool_port
        self._stream_port = stream_port
        self.rate_limit_config = rate_limit_config or RateLimitConfig()
        self.retry_config = retry_config or RetryConfig()
        self.spool_config = spool_config or SpoolConfig()
        self.default_timeout = default_timeout
        self._is_closed = False

    async def __aenter__(self) -> AsyncTransportClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Asynchronously closes client resources."""
        self._is_closed = True

    @property
    def is_closed(self) -> bool:
        """Returns True if the client is closed."""
        return self._is_closed

    @property
    def spool_depth(self) -> int:
        """Returns the number of currently spooled requests."""
        if self._spool_port is None:
            return 0
        return self._spool_port.depth

    @property
    def is_stream_alive(self) -> bool:
        """Returns True if the telemetry stream watchdog reports active."""
        if self._stream_port is None:
            return False
        return self._stream_port.is_alive

    def _normalize_body(self, body: bytes | str | None) -> bytes:
        """Validates and normalizes payload body into raw bytes."""
        if body is None:
            return b""
        if isinstance(body, bytes):
            return body
        if isinstance(body, str):
            return body.encode("utf-8")
        raise InvalidPayloadTypeError(type(body))

    def _build_request(
        self,
        url: str,
        method: str,
        body: bytes | str | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpRequestDTO:
        """Constructs an immutable HttpRequestDTO."""
        norm_body = self._normalize_body(body)
        hdrs: dict[str, str] = dict(headers) if headers else {}
        target_url = url
        if params:
            import urllib.parse

            query_string = urllib.parse.urlencode(params)
            sep = "&" if "?" in target_url else "?"
            target_url = f"{target_url}{sep}{query_string}"

        return HttpRequestDTO(
            url=target_url,
            method=method.upper(),
            headers=hdrs,
            body=norm_body,
            timeout=timeout if timeout is not None else self.default_timeout,
        )

    async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
        """Asynchronously dispatches an immutable HttpRequestDTO."""
        if self._transport_port is None:
            raise RuntimeError("AsyncHttpTransportPort is not configured on this client")
        return await self._transport_port.send_async(request)

    async def get_async(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponseDTO:
        """Asynchronously dispatches an HTTP GET request."""
        req = self._build_request(url, "GET", None, headers, params, timeout)
        return await self.send_async(req)

    async def post_async(
        self,
        url: str,
        *,
        body: bytes | str | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponseDTO:
        """Asynchronously dispatches an HTTP POST request."""
        req = self._build_request(url, "POST", body, headers, params, timeout)
        return await self.send_async(req)

    async def put_async(
        self,
        url: str,
        *,
        body: bytes | str | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponseDTO:
        """Asynchronously dispatches an HTTP PUT request."""
        req = self._build_request(url, "PUT", body, headers, params, timeout)
        return await self.send_async(req)

    async def delete_async(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponseDTO:
        """Asynchronously dispatches an HTTP DELETE request."""
        req = self._build_request(url, "DELETE", None, headers, params, timeout)
        return await self.send_async(req)

    async def send_buffered_async(
        self,
        request: HttpRequestDTO | None = None,
        *,
        url: str | None = None,
        method: str = "POST",
        body: bytes | str | None = None,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        timeout: float | None = None,
    ) -> bool:
        """Sends immediately or buffers to offline spool if network is unreachable."""
        req = request or self._build_request(url or "", method, body, headers, params, timeout)
        try:
            res = await self.send_async(req)
            return res.is_success
        except Exception:
            if self._spool_port is not None:
                return self._spool_port.enqueue(req)
            raise

    async def drain_spool_async(self, batch_size: int = 50) -> int:
        """Drains enqueued requests and dispatches in FIFO order."""
        if self._spool_port is None:
            return 0
        return self._spool_port.drain(batch_size)

    def open_stream(
        self, endpoint: str = "/api/v1/stream", topic: str | None = None
    ) -> AsyncIterator[RawStreamEventDTO]:
        """Subscribes to live Server-Sent Events from local ed-telemetry."""
        if self._stream_port is None:
            raise RuntimeError("TelemetryStreamPort is not configured on this client")
        return self._stream_port.open_stream(endpoint, topic)
