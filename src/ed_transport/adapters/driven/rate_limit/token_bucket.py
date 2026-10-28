"""Thread-safe token bucket rate limiter adapter supporting sync and async."""

from __future__ import annotations

import asyncio
import threading
import time
from typing import ClassVar

from ....core.ports.driven.rate_limiter_port import RateLimiterPort


class TokenBucketRateLimiter(RateLimiterPort):
    """Thread-safe token bucket rate limiter tracking capacity per destination."""

    DEFAULT_RPS: ClassVar[float] = 5.0
    DEFAULT_BURST: ClassVar[int] = 10

    def __init__(
        self,
        default_rps: float = DEFAULT_RPS,
        default_burst: int = DEFAULT_BURST,
        destination_rules: dict[str, tuple[float, int]] | None = None,
    ) -> None:
        self._default_rps = default_rps
        self._default_burst = default_burst
        self._rules = destination_rules or {}
        self._buckets: dict[
            str, tuple[float, float]
        ] = {}  # destination -> (tokens, last_refill_time)
        self._sync_lock = threading.Lock()
        self._async_lock = asyncio.Lock()

    def acquire(self, destination: str, timeout: float | None = None) -> bool:
        """Blocks synchronously until a token is available or timeout expires."""
        start_time = time.monotonic()
        rps, burst = self._get_rule(destination)

        while True:
            with self._sync_lock:
                now = time.monotonic()
                tokens, last_refill = self._refill(destination, now, rps, burst)
                if tokens >= 1.0:
                    self._buckets[destination] = (tokens - 1.0, now)
                    return True

                tokens_needed = 1.0 - tokens
                wait_time = tokens_needed / rps

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed + wait_time > timeout:
                    return False

            sleep_duration = min(wait_time, 0.05)
            time.sleep(sleep_duration)

    async def acquire_async(self, destination: str, timeout: float | None = None) -> bool:
        """Waits asynchronously until a token is available or timeout expires."""
        start_time = time.monotonic()
        rps, burst = self._get_rule(destination)

        while True:
            async with self._async_lock:
                now = time.monotonic()
                tokens, last_refill = self._refill(destination, now, rps, burst)
                if tokens >= 1.0:
                    self._buckets[destination] = (tokens - 1.0, now)
                    return True

                tokens_needed = 1.0 - tokens
                wait_time = tokens_needed / rps

            if timeout is not None:
                elapsed = time.monotonic() - start_time
                if elapsed + wait_time > timeout:
                    return False

            sleep_duration = min(wait_time, 0.05)
            await asyncio.sleep(sleep_duration)

    def _get_rule(self, destination: str) -> tuple[float, int]:
        """Returns (rps, burst) configured for destination or default."""
        return self._rules.get(destination, (self._default_rps, self._default_burst))

    def _refill(self, destination: str, now: float, rps: float, burst: int) -> tuple[float, float]:
        """Calculates current token count after elapsed refill interval."""
        tokens, last_refill = self._buckets.get(destination, (float(burst), now))
        elapsed = max(0.0, now - last_refill)
        refilled = min(float(burst), tokens + (elapsed * rps))
        return (refilled, now)
