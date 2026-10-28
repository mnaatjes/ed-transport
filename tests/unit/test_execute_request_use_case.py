"""Unit tests for ExecuteHttpRequestUseCase and AsyncExecuteHttpRequestUseCase."""

from __future__ import annotations

import pytest

from ed_transport.core.domain.exceptions import (
    MaxRetriesExceededError,
    RateLimitExceededError,
    TransportConnectionError,
)
from ed_transport.core.domain.models import RetryConfig
from ed_transport.core.ports.dto.transport_dto import HttpRequestDTO, HttpResponseDTO
from ed_transport.core.use_cases.execute_request import ExecuteHttpRequestUseCase
from ed_transport.core.use_cases.execute_request_async import AsyncExecuteHttpRequestUseCase
from tests.doubles.fake_adapters import (
    FakeAsyncTransportEngineAdapter,
    FakeRateLimiterAdapter,
    FakeTransportEngineAdapter,
)


def test_execute_request_success() -> None:
    engine = FakeTransportEngineAdapter()
    rate_limiter = FakeRateLimiterAdapter(should_grant=True)
    use_case = ExecuteHttpRequestUseCase(engine=engine, rate_limiter=rate_limiter)

    req = HttpRequestDTO(url="https://api.frontier.ed/status", method="GET")
    resp = use_case.send(req)

    assert resp.status_code == 200
    assert len(engine.sent_requests) == 1
    assert "api.frontier.ed" in rate_limiter.acquired_calls


def test_execute_request_rate_limit_exceeded() -> None:
    engine = FakeTransportEngineAdapter()
    rate_limiter = FakeRateLimiterAdapter(should_grant=False)
    use_case = ExecuteHttpRequestUseCase(engine=engine, rate_limiter=rate_limiter)

    req = HttpRequestDTO(url="https://api.frontier.ed/status", method="GET")
    with pytest.raises(RateLimitExceededError):
        use_case.send(req)

    assert len(engine.sent_requests) == 0


def test_execute_request_retries_on_503_and_recovers() -> None:
    engine = FakeTransportEngineAdapter()
    engine.responses = [
        HttpResponseDTO(status_code=503, headers={}, body=b"Service Unavailable"),
        HttpResponseDTO(status_code=200, headers={}, body=b'{"ok": true}'),
    ]
    rate_limiter = FakeRateLimiterAdapter(should_grant=True)
    retry_cfg = RetryConfig(max_retries=2, base_delay=0.01, max_backoff=0.05)
    use_case = ExecuteHttpRequestUseCase(
        engine=engine,
        rate_limiter=rate_limiter,
        retry_config=retry_cfg,
    )

    req = HttpRequestDTO(url="https://api.frontier.ed/status", method="GET")
    resp = use_case.send(req)

    assert resp.status_code == 200
    assert len(engine.sent_requests) == 2


def test_execute_request_exhausts_retries() -> None:
    # Mock engine that raises TransportConnectionError on send
    class FailingEngine(FakeTransportEngineAdapter):
        def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
            raise TransportConnectionError(endpoint=request.url, details="Refused")

    rate_limiter = FakeRateLimiterAdapter(should_grant=True)
    retry_cfg = RetryConfig(max_retries=2, base_delay=0.01, max_backoff=0.05)
    use_case = ExecuteHttpRequestUseCase(
        engine=FailingEngine(),
        rate_limiter=rate_limiter,
        retry_config=retry_cfg,
    )

    req = HttpRequestDTO(url="https://api.frontier.ed/status", method="GET")
    with pytest.raises(MaxRetriesExceededError) as exc_info:
        use_case.send(req)

    assert exc_info.value.total_attempts == 3


@pytest.mark.asyncio
async def test_async_execute_request_success() -> None:
    engine = FakeAsyncTransportEngineAdapter()
    rate_limiter = FakeRateLimiterAdapter(should_grant=True)
    use_case = AsyncExecuteHttpRequestUseCase(engine=engine, rate_limiter=rate_limiter)

    req = HttpRequestDTO(url="https://api.frontier.ed/status", method="GET")
    resp = await use_case.send_async(req)

    assert resp.status_code == 200
    assert len(engine.sent_requests) == 1
    assert "api.frontier.ed" in rate_limiter.acquired_calls
