"""Abstract driven secondary SPI port for rate limiter adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..base import DrivenPort


@runtime_checkable
class RateLimiterPort(DrivenPort, Protocol):
    """Secondary driven SPI port for destination rate-limiting enforcement."""

    def acquire(self, destination: str, timeout: float | None = None) -> bool:
        """Blocks synchronously until a token is available or timeout expires."""
        ...

    async def acquire_async(self, destination: str, timeout: float | None = None) -> bool:
        """Asynchronously waits until a token is available or timeout expires."""
        ...
