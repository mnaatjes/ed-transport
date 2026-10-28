"""Server-Sent Events (SSE) telemetry stream engine adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx

from ....core.domain.exceptions import (
    TransportConnectionError,
    TransportError,
    TransportTimeoutError,
)
from ....core.ports.driven.stream_engine_port import StreamEnginePort
from ....core.ports.dto.transport_dto import RawStreamEventDTO


class SseStreamEngineAdapter(StreamEnginePort):
    """Asynchronous HTTP SSE streaming engine parsing standard event frames."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=None)
        self._owns_client = client is None

    async def open_stream(
        self, endpoint: str, topic: str | None = None
    ) -> AsyncIterator[RawStreamEventDTO]:
        """Streams chunked response lines, parsing SSE frames (event, data, id)."""
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
        }
        params = {"topic": topic} if topic else {}

        try:
            async with self._client.stream(
                "GET", endpoint, headers=headers, params=params
            ) as response:
                if response.status_code != 200:
                    raise TransportError(
                        f"SSE stream endpoint returned non-200 status: {response.status_code}"
                    )

                event_type = "message"
                data_lines: list[str] = []
                event_id: str | None = None

                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        # Empty line marks end of event frame
                        if data_lines:
                            yield RawStreamEventDTO(
                                event_type=event_type,
                                data="\n".join(data_lines),
                                id=event_id,
                            )
                            event_type = "message"
                            data_lines = []
                        continue

                    if line.startswith(":"):
                        # SSE comment line, ignore
                        continue

                    if ":" in line:
                        field, value = line.split(":", 1)
                        value = value.lstrip()
                    else:
                        field, value = line, ""

                    if field == "event":
                        event_type = value
                    elif field == "data":
                        data_lines.append(value)
                    elif field == "id":
                        event_id = value

                # Flush any trailing event
                if data_lines:
                    yield RawStreamEventDTO(
                        event_type=event_type,
                        data="\n".join(data_lines),
                        id=event_id,
                    )

        except (httpx.ConnectTimeout, httpx.ReadTimeout) as err:
            raise TransportTimeoutError(endpoint=endpoint, timeout_seconds=0.0) from err
        except (httpx.ConnectError, httpx.NetworkError) as err:
            raise TransportConnectionError(endpoint=endpoint, details=str(err)) from err
        except httpx.HTTPError as err:
            raise TransportError(f"Stream connection failed for '{endpoint}': {err}") from err

    async def aclose(self) -> None:
        """Closes the underlying async client."""
        if self._owns_client:
            await self._client.aclose()
