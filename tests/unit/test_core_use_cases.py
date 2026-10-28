"""Unit tests for core transport and spool use cases."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from ed_transport.core.domain.exceptions import (
    MaxRetriesExceededError,
    RateLimitExceededError,
    TransportConnectionError,
    TransportTimeoutError,
)
from ed_transport.core.domain.health import HealthStatus
from ed_transport.core.domain.models import RetryConfig
from ed_transport.core.ports.dto.transport_dto import (
    HttpRequestDTO,
    HttpResponseDTO,
    RawStreamEventDTO,
    SpoolRecordDTO,
)
from ed_transport.core.use_cases.check_health import CheckHealthUseCase
from ed_transport.core.use_cases.consume_stream import ConsumeTelemetryStreamUseCase
from ed_transport.core.use_cases.drain_spool import (
    AsyncDrainSpoolBufferUseCase,
    DrainSpoolBufferUseCase,
)
from ed_transport.core.use_cases.execute_request import ExecuteHttpRequestUseCase
from ed_transport.core.use_cases.execute_request_async import (
    AsyncExecuteHttpRequestUseCase,
)
from tests.doubles.fake_adapters import (
    FakeAsyncTransportEngineAdapter,
    FakeRateLimiterAdapter,
    FakeSpoolStorageAdapter,
    FakeStreamEngineAdapter,
    FakeTransportEngineAdapter,
)


class TestExecuteHttpRequestUseCase:
    """Verifies synchronous request execution, retries, and rate limiting."""

    def test_successful_request_on_first_attempt(self) -> None:
        engine = FakeTransportEngineAdapter()
        limiter = FakeRateLimiterAdapter()
        use_case = ExecuteHttpRequestUseCase(engine=engine, rate_limiter=limiter)

        req = HttpRequestDTO(url="https://api.eddn.io/push")
        resp = use_case.send(req)

        assert resp.status_code == 200
        assert len(engine.sent_requests) == 1

    def test_retry_on_503_eventual_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sleep_mock = MagicMock()
        monkeypatch.setattr("time.sleep", sleep_mock)

        responses = [
            HttpResponseDTO(status_code=503, headers={}, body=b"Unavailable"),
            HttpResponseDTO(status_code=200, headers={}, body=b"Success"),
        ]

        class SequenceEngine(FakeTransportEngineAdapter):
            def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
                self.sent_requests.append(request)
                return responses.pop(0)

        engine = SequenceEngine()
        limiter = FakeRateLimiterAdapter()
        retry_cfg = RetryConfig(max_retries=3, base_delay=0.1, max_backoff=1.0)
        use_case = ExecuteHttpRequestUseCase(
            engine=engine, rate_limiter=limiter, retry_config=retry_cfg
        )

        resp = use_case.send(HttpRequestDTO(url="https://api.eddn.io/push"))
        assert resp.status_code == 200
        assert len(engine.sent_requests) == 2
        assert sleep_mock.call_count == 1

    def test_retry_exhaustion_on_network_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("time.sleep", lambda _: None)

        class FailingEngine(FakeTransportEngineAdapter):
            def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
                raise TransportConnectionError(endpoint=request.url, details="Refused")

        use_case = ExecuteHttpRequestUseCase(
            engine=FailingEngine(),
            rate_limiter=FakeRateLimiterAdapter(),
            retry_config=RetryConfig(max_retries=2, base_delay=0.01),
        )

        with pytest.raises(MaxRetriesExceededError) as exc_info:
            use_case.send(HttpRequestDTO(url="https://api.eddn.io/push"))

        assert exc_info.value.total_attempts == 3  # Initial + 2 retries
        assert isinstance(exc_info.value.last_error, TransportConnectionError)

    def test_rate_limit_rejection_raises_error(self) -> None:
        limiter = FakeRateLimiterAdapter(should_grant=False)
        engine = FakeTransportEngineAdapter()
        use_case = ExecuteHttpRequestUseCase(engine=engine, rate_limiter=limiter)

        with pytest.raises(RateLimitExceededError):
            use_case.send(HttpRequestDTO(url="https://api.eddn.io/push"))


class TestAsyncExecuteHttpRequestUseCase:
    """Verifies asynchronous request execution, retries, and rate limiting."""

    @pytest.mark.asyncio
    async def test_async_success_first_attempt(self) -> None:
        engine = FakeAsyncTransportEngineAdapter()
        limiter = FakeRateLimiterAdapter()
        use_case = AsyncExecuteHttpRequestUseCase(engine=engine, rate_limiter=limiter)

        resp = await use_case.send_async(HttpRequestDTO(url="https://api.eddn.io/async"))
        assert resp.status_code == 200
        assert len(engine.sent_requests) == 1

    @pytest.mark.asyncio
    async def test_async_retry_on_500_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sleep_mock = MagicMock()

        async def fake_sleep(dur: float) -> None:
            sleep_mock(dur)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        responses = [
            HttpResponseDTO(status_code=500, headers={}, body=b"Server Error"),
            HttpResponseDTO(status_code=200, headers={}, body=b"Recovered"),
        ]

        class AsyncSeqEngine(FakeAsyncTransportEngineAdapter):
            async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
                self.sent_requests.append(request)
                return responses.pop(0)

        use_case = AsyncExecuteHttpRequestUseCase(
            engine=AsyncSeqEngine(),
            rate_limiter=FakeRateLimiterAdapter(),
            retry_config=RetryConfig(max_retries=2, base_delay=0.01),
        )

        resp = await use_case.send_async(HttpRequestDTO(url="https://api.eddn.io/async"))
        assert resp.status_code == 200
        assert sleep_mock.call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_exhaustion_on_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def dummy_sleep(_: float) -> None:
            pass

        monkeypatch.setattr(asyncio, "sleep", dummy_sleep)

        class AsyncTimeoutEngine(FakeAsyncTransportEngineAdapter):
            async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
                raise TransportTimeoutError(endpoint=request.url, timeout_seconds=5.0)

        use_case = AsyncExecuteHttpRequestUseCase(
            engine=AsyncTimeoutEngine(),
            rate_limiter=FakeRateLimiterAdapter(),
            retry_config=RetryConfig(max_retries=1, base_delay=0.01),
        )

        with pytest.raises(MaxRetriesExceededError) as exc_info:
            await use_case.send_async(HttpRequestDTO(url="https://api.eddn.io/async"))

        assert exc_info.value.total_attempts == 2
        assert isinstance(exc_info.value.last_error, TransportTimeoutError)

    @pytest.mark.asyncio
    async def test_async_rate_limit_exceeded(self) -> None:
        limiter = FakeRateLimiterAdapter(should_grant=False)
        engine = FakeAsyncTransportEngineAdapter()
        use_case = AsyncExecuteHttpRequestUseCase(engine=engine, rate_limiter=limiter)

        with pytest.raises(RateLimitExceededError):
            await use_case.send_async(HttpRequestDTO(url="https://api.eddn.io/async"))


class TestConsumeTelemetryStreamUseCase:
    """Verifies SSE telemetry streaming, cursor retention, and backoff loops."""

    @pytest.mark.asyncio
    async def test_consume_stream_events_clean_exit(self) -> None:
        engine = FakeStreamEngineAdapter()
        engine.events_to_yield = [
            RawStreamEventDTO(event_type="event", data="one", id="1"),
            RawStreamEventDTO(event_type="event", data="two", id="2"),
        ]
        use_case = ConsumeTelemetryStreamUseCase(stream_engine=engine)

        received: list[RawStreamEventDTO] = []
        async for evt in use_case.open_stream(endpoint="/telemetry", topic="journal"):
            received.append(evt)

        assert len(received) == 2
        assert received[0].data == "one"
        assert received[1].data == "two"
        assert use_case.is_alive is False

    @pytest.mark.asyncio
    async def test_consume_stream_reconnect_on_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sleep_mock = MagicMock()

        async def fake_sleep(dur: float) -> None:
            sleep_mock(dur)

        monkeypatch.setattr(asyncio, "sleep", fake_sleep)

        # First connection yields 1 event then errors; second connection finishes
        call_count = 0

        class FlakyStreamEngine(FakeStreamEngineAdapter):
            async def open_stream(self, endpoint: str, topic: str | None = None):  # type: ignore[override]
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    yield RawStreamEventDTO(event_type="event", data="first", id="cur-1")
                    raise ConnectionResetError("Socket broken")
                else:
                    yield RawStreamEventDTO(event_type="event", data="second", id="cur-2")

        use_case = ConsumeTelemetryStreamUseCase(
            stream_engine=FlakyStreamEngine(),
            base_reconnect_delay=0.01,
            max_reconnect_delay=0.1,
        )

        consumed: list[str] = []
        async for evt in use_case.open_stream(endpoint="/telemetry"):
            consumed.append(evt.data)

        assert consumed == ["first", "second"]
        assert call_count == 2
        assert sleep_mock.call_count == 1

    @pytest.mark.asyncio
    async def test_consume_stream_cancellation(self) -> None:
        class InfiniteStreamEngine(FakeStreamEngineAdapter):
            async def open_stream(self, endpoint: str, topic: str | None = None):  # type: ignore[override]
                while True:
                    yield RawStreamEventDTO(event_type="ping", data="{}")
                    await asyncio.sleep(0.01)

        use_case = ConsumeTelemetryStreamUseCase(stream_engine=InfiniteStreamEngine())

        async def run_consumer() -> None:
            async for _ in use_case.open_stream("/telemetry"):
                pass

        task = asyncio.create_task(run_consumer())
        await asyncio.sleep(0.02)
        assert use_case.is_alive is True
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert use_case.is_alive is False


class TestDrainSpoolUseCases:
    """Verifies synchronous and asynchronous spool buffer draining interactors."""

    def test_sync_drain_success_and_poison_pill_discard(self) -> None:
        storage = FakeSpoolStorageAdapter()
        req1 = HttpRequestDTO(url="https://api.eddn.io/1")
        req2 = HttpRequestDTO(url="https://api.eddn.io/2")  # Will return 400 Bad Request
        req3 = HttpRequestDTO(url="https://api.eddn.io/3")

        storage.push(SpoolRecordDTO(sequence_id=1, request=req1, created_at=1.0))
        storage.push(SpoolRecordDTO(sequence_id=2, request=req2, created_at=2.0))
        storage.push(SpoolRecordDTO(sequence_id=3, request=req3, created_at=3.0))

        class MockTransport:
            def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
                if request.url.endswith("/2"):
                    return HttpResponseDTO(status_code=400, headers={}, body=b"Bad Request")
                return HttpResponseDTO(status_code=200, headers={}, body=b"OK")

        use_case = DrainSpoolBufferUseCase(storage=storage, transport=MockTransport())  # type: ignore[arg-type]
        assert use_case.depth == 3

        drained = use_case.drain(batch_size=10)
        assert drained == 3
        assert use_case.depth == 0

    def test_sync_drain_halts_on_server_error_and_network_drop(self) -> None:
        storage = FakeSpoolStorageAdapter()
        req1 = HttpRequestDTO(url="https://api.eddn.io/1")
        req2 = HttpRequestDTO(url="https://api.eddn.io/2")
        storage.push(SpoolRecordDTO(sequence_id=1, request=req1, created_at=1.0))
        storage.push(SpoolRecordDTO(sequence_id=2, request=req2, created_at=2.0))

        class ErrorTransport:
            def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
                return HttpResponseDTO(status_code=503, headers={}, body=b"Unavailable")

        use_case = DrainSpoolBufferUseCase(storage=storage, transport=ErrorTransport())  # type: ignore[arg-type]
        drained = use_case.drain(batch_size=5)
        assert drained == 0
        assert use_case.depth == 2  # Not popped

        class DropTransport:
            def send(self, request: HttpRequestDTO) -> HttpResponseDTO:
                raise TransportConnectionError(endpoint=request.url)

        drop_use_case = DrainSpoolBufferUseCase(storage=storage, transport=DropTransport())  # type: ignore[arg-type]
        assert drop_use_case.drain(batch_size=5) == 0
        assert drop_use_case.depth == 2

    @pytest.mark.asyncio
    async def test_async_drain_batch_processing(self) -> None:
        storage = FakeSpoolStorageAdapter()
        req1 = HttpRequestDTO(url="https://api.eddn.io/async/1")
        req2 = HttpRequestDTO(url="https://api.eddn.io/async/2")
        storage.push(SpoolRecordDTO(sequence_id=1, request=req1, created_at=1.0))
        storage.push(SpoolRecordDTO(sequence_id=2, request=req2, created_at=2.0))

        class AsyncMockTransport:
            async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
                if request.url.endswith("/2"):
                    return HttpResponseDTO(status_code=500, headers={}, body=b"Server Error")
                return HttpResponseDTO(status_code=200, headers={}, body=b"OK")

        async_use_case = AsyncDrainSpoolBufferUseCase(
            storage=storage,
            transport=AsyncMockTransport(),  # type: ignore[arg-type]
        )
        assert async_use_case.depth == 2

        # Sync drain method returns 0
        assert async_use_case.drain() == 0

        # Async drain processes first, stops at second due to 500
        drained = await async_use_case.drain_async(batch_size=10)
        assert drained == 1
        assert async_use_case.depth == 1

        # Enqueue via use case helper
        assert async_use_case.enqueue(HttpRequestDTO(url="https://api.eddn.io/async/3")) is True
        assert async_use_case.depth == 2

    @pytest.mark.asyncio
    async def test_async_drain_network_drop(self) -> None:
        storage = FakeSpoolStorageAdapter()
        req = HttpRequestDTO(url="https://api.eddn.io/async/drop")
        storage.push(SpoolRecordDTO(sequence_id=1, request=req, created_at=1.0))

        class AsyncDropTransport:
            async def send_async(self, request: HttpRequestDTO) -> HttpResponseDTO:
                raise TransportTimeoutError(endpoint=request.url, timeout_seconds=5.0)

        use_case = AsyncDrainSpoolBufferUseCase(
            storage=storage,
            transport=AsyncDropTransport(),  # type: ignore[arg-type]
        )
        drained = await use_case.drain_async(batch_size=5)
        assert drained == 0
        assert use_case.depth == 1


class TestCheckHealthUseCase:
    """Verifies operational health check use case and status mapping."""

    def test_health_check_healthy(self) -> None:
        probe = MagicMock()
        probe.is_operational.return_value = True
        use_case = CheckHealthUseCase(probe=probe, service_name="ed-transport-telemetry")

        health = use_case.check_health()
        assert health.status == HealthStatus.HEALTHY
        assert health.service_name == "ed-transport-telemetry"

    def test_health_check_unhealthy(self) -> None:
        probe = MagicMock()
        probe.is_operational.return_value = False
        use_case = CheckHealthUseCase(probe=probe, service_name="ed-transport-telemetry")

        health = use_case.check_health()
        assert health.status == HealthStatus.UNHEALTHY
