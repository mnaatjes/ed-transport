"""Unit tests for TokenBucketRateLimiter adapter."""

from __future__ import annotations

import pytest

from ed_transport.adapters.driven.rate_limit.token_bucket import TokenBucketRateLimiter


def test_token_bucket_acquire_within_burst() -> None:
    limiter = TokenBucketRateLimiter(default_rps=10.0, default_burst=5)
    for _ in range(5):
        assert limiter.acquire("api.ed.test", timeout=0.01) is True


def test_token_bucket_exhaustion_and_timeout() -> None:
    limiter = TokenBucketRateLimiter(default_rps=1.0, default_burst=1)
    # First token granted immediately
    assert limiter.acquire("api.ed.test", timeout=0.01) is True
    # Immediate second attempt times out
    assert limiter.acquire("api.ed.test", timeout=0.02) is False


@pytest.mark.asyncio
async def test_token_bucket_async_acquire() -> None:
    limiter = TokenBucketRateLimiter(default_rps=10.0, default_burst=2)
    assert await limiter.acquire_async("api.ed.test", timeout=0.01) is True
    assert await limiter.acquire_async("api.ed.test", timeout=0.01) is True
