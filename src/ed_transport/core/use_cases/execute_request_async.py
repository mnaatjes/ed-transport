"""Asynchronous request execution use case orchestrating retries and rate limiting."""

from __future__ import annotations

import asyncio
import logging
import random

from ..domain.exceptions import (
    MaxRetriesExceededError,
    RateLimitExceededError,
    TransportConnectionError,
    TransportTimeoutError,
)
from ..domain.models import RateLimitConfig, RetryConfig
from ..ports.driven.engine_port import AsyncTransportEnginePort
from ..ports.driven.rate_limiter_port import RateLimiterPort
from ..ports.driving.transport_port import AsyncTransportPort
from ..ports.dto.transport_dto import HttpRequestDTO, HttpResponseDTO

_logger = logging.getLogger(__name__)


class AsyncExecuteHttpRequestUseCase(AsyncTransportPort):
    """Asynchronous interactor dispatching requests via async engine port."""

    def __init__(
        self,
        engine: AsyncTransportEnginePort,
        rate_limiter: RateLimiterPort,
        retry_config: RetryConfig | None = None,
        rate_limit_config: RateLimitConfig | None = None,
    ) -> None:
        self._engine = engine
        self._rate_limiter = rate_limiter
        self._retry_config = retry_config or RetryConfig()
        self._rate_limit_config = rate_limit_config or RateLimitConfig()

    async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
        """Asynchronously executes resilient request dispatch honoring rate limits and retries."""
        destination = self._extract_destination(request.url)
        acquired = await self._rate_limiter.acquire_async(destination, timeout=request.timeout)
        if not acquired:
            raise RateLimitExceededError(
                destination_key=destination,
                retry_after_seconds=1.0 / self._rate_limit_config.requests_per_second,
            )

        last_error: Exception | None = None
        attempt = 0
        max_retries = self._retry_config.max_retries

        while attempt <= max_retries:
            attempt += 1
            try:
                response = await self._engine.send_async(request)
                if response.status_code not in self._retry_config.retryable_statuses:
                    return response

                if attempt > max_retries:
                    return response

                backoff = self._calculate_backoff(attempt)
                _logger.warning(
                    "Retrying async request to %s (status %d, attempt %d/%d, backoff %.2fs)",
                    request.url,
                    response.status_code,
                    attempt,
                    max_retries,
                    backoff,
                )
                await asyncio.sleep(backoff)

            except (TransportConnectionError, TransportTimeoutError) as err:
                last_error = err
                if attempt > max_retries:
                    raise MaxRetriesExceededError(
                        endpoint=request.url,
                        total_attempts=attempt,
                        last_error=last_error,
                    ) from last_error

                backoff = self._calculate_backoff(attempt)
                _logger.warning(
                    "Retrying async request to %s after error %s (attempt %d/%d, backoff %.2fs)",
                    request.url,
                    err,
                    attempt,
                    max_retries,
                    backoff,
                )
                await asyncio.sleep(backoff)

        raise MaxRetriesExceededError(
            endpoint=request.url,
            total_attempts=attempt,
            last_error=last_error,
        ) from last_error

    def _extract_destination(self, url: str) -> str:
        """Derives a destination key from the target URL."""
        if "//" in url:
            after_proto = url.split("//", 1)[1]
            host_port = after_proto.split("/", 1)[0].split("?", 1)[0]
            return host_port or "default"
        return "default"

    def _calculate_backoff(self, attempt: int) -> float:
        """Computes exponential backoff with randomized decorrelated jitter."""
        exponential = self._retry_config.base_delay * (2 ** (attempt - 1))
        jitter = random.uniform(0.0, self._retry_config.base_delay)
        return min(self._retry_config.max_backoff, exponential + jitter)
