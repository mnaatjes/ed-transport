"""Driven infrastructure adapters for synchronous and asynchronous HTTP transmission."""

from __future__ import annotations

import httpx

from ....core.domain.exceptions import (
    TransportConnectionError,
    TransportError,
    TransportTimeoutError,
)
from ....core.ports.driven.engine_port import (
    AsyncTransportEnginePort,
    TransportEnginePort,
)
from ....core.ports.dto.transport_dto import HttpRequestDTO, HttpResponseDTO


class HttpxSyncEngineAdapter(TransportEnginePort):
    """Synchronous network transport adapter powered by httpx.Client."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(follow_redirects=True)
        self._owns_client = client is None

    def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
        """Sends an HTTP request synchronously, translating httpx exceptions to domain errors."""
        try:
            resp = self._client.request(
                method=request.method,
                url=request.url,
                headers=dict(request.headers),
                content=request.body,
                timeout=request.timeout,
            )
            return HttpResponseDTO(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp.content,
            )
        except (
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
        ) as err:
            raise TransportTimeoutError(
                endpoint=request.url,
                timeout_seconds=request.timeout,
            ) from err
        except (httpx.ConnectError, httpx.NetworkError) as err:
            raise TransportConnectionError(
                endpoint=request.url,
                details=str(err),
            ) from err
        except httpx.HTTPError as err:
            raise TransportError(f"HTTP transport failed for '{request.url}': {err}") from err

    def close(self) -> None:
        """Closes the underlying httpx client."""
        if self._owns_client:
            self._client.close()


class HttpxAsyncEngineAdapter(AsyncTransportEnginePort):
    """Asynchronous network transport adapter powered by httpx.AsyncClient."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(follow_redirects=True)
        self._owns_client = client is None

    async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
        """Sends an HTTP request asynchronously, translating httpx exceptions to domain errors."""
        try:
            resp = await self._client.request(
                method=request.method,
                url=request.url,
                headers=dict(request.headers),
                content=request.body,
                timeout=request.timeout,
            )
            return HttpResponseDTO(
                status_code=resp.status_code,
                headers=dict(resp.headers),
                body=resp.content,
            )
        except (
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
        ) as err:
            raise TransportTimeoutError(
                endpoint=request.url,
                timeout_seconds=request.timeout,
            ) from err
        except (httpx.ConnectError, httpx.NetworkError) as err:
            raise TransportConnectionError(
                endpoint=request.url,
                details=str(err),
            ) from err
        except httpx.HTTPError as err:
            raise TransportError(f"Async HTTP transport failed for '{request.url}': {err}") from err

    async def aclose(self) -> None:
        """Closes the underlying async httpx client."""
        if self._owns_client:
            await self._client.aclose()
