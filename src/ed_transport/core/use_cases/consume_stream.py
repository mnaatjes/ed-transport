"""Telemetry stream consumption use case orchestrating reconnection backoff and event cursors."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import AsyncIterator

from ..ports.driven.stream_engine_port import StreamEnginePort
from ..ports.driving.stream_port import TelemetryStreamPort
from ..ports.dto.transport_dto import RawStreamEventDTO

_logger = logging.getLogger(__name__)


class ConsumeTelemetryStreamUseCase(TelemetryStreamPort):
    """Asynchronous generator consuming SSE telemetry streams with recovery."""

    def __init__(
        self,
        stream_engine: StreamEnginePort,
        base_reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
    ) -> None:
        self._stream_engine = stream_engine
        self._base_delay = base_reconnect_delay
        self._max_delay = max_reconnect_delay
        self._is_alive = False

    async def open_stream(
        self, endpoint: str = "/api/v1/stream", topic: str | None = None
    ) -> AsyncIterator[RawStreamEventDTO]:
        """Opens persistent stream and yields raw decoded stream frames."""
        consecutive_failures = 0
        last_event_id: str | None = None

        while True:
            try:
                self._is_alive = True
                stream = self._stream_engine.open_stream(endpoint, topic=topic)
                consecutive_failures = 0

                async for event in stream:
                    if event.id:
                        last_event_id = event.id
                    yield event

                # Stream ended cleanly, reset alive flag
                self._is_alive = False
                break

            except asyncio.CancelledError:
                self._is_alive = False
                raise

            except Exception as err:
                self._is_alive = False
                consecutive_failures += 1
                backoff = self._calculate_reconnect_backoff(consecutive_failures)
                _logger.warning(
                    "Telemetry stream dropped (%s); retry in %.2fs (cursor=%s, attempt=%d)",
                    err,
                    backoff,
                    last_event_id,
                    consecutive_failures,
                )
                await asyncio.sleep(backoff)

    @property
    def is_alive(self) -> bool:
        """Returns True if the underlying stream connection is currently active."""
        return self._is_alive

    def _calculate_reconnect_backoff(self, attempt: int) -> float:
        """Computes exponential backoff with randomized decorrelated jitter clamped to max delay."""
        exponential = self._base_delay * (2 ** (attempt - 1))
        jitter = random.uniform(0.0, self._base_delay)
        return min(self._max_delay, exponential + jitter)
