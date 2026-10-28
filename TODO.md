# Implementation Tasks: ADR 0006 & SDD 0006

Based on [ADR 0006](architecture/adr/0006_comprehensive_test_harness_and_fault_injection_framework.md) and [SDD 0006](architecture/designs/0006_comprehensive_test_harness_and_fault_injection_framework.md).

## Task 1: Core Domain & DTO Tests
- [x] `tests/unit/test_domain_models.py`:
  - `HttpRequest` validation (invalid URL scheme, empty URL, invalid method, header coercion, immutability)
  - `HttpResponse` validation (status code ranges 100-599, binary integrity, latency validation)
  - `RetryPolicy` validation (jitter bounds, exponential multiplier $\ge 1.0$, max backoff caps)
  - `RateLimitRule` validation (sustained/burst positivity, interval validity)
- [x] Domain exceptions:
  - Hierarchy validation (`DomainValidationError`, `TransportError`, `TransportTimeoutError`, `TransportConnectionError`, `SpoolStorageError`)
  - Error formatting and causal chaining (`from err`)
- [x] DTO validation:
  - Boundary DTO tests (`HttpRequestDTO`, `HttpResponseDTO`, `RawStreamEventDTO`, `SpoolRecordDTO`)

## Task 2: Core Use Cases Comprehensive Tests
- [x] `tests/unit/test_core_use_cases.py`:
  - Sync request execution (`ExecuteHttpRequestUseCase`): retries on 5xx/429 with jitter, non-retryable 4xx, rate limiter token exhaustion wait
  - Async request execution (`AsyncExecuteHttpRequestUseCase`): async retries, jitter, sleep interactor, timeout translation
  - SSE stream consumption (`ConsumeTelemetryStreamUseCase`): continuous iteration, auto-reconnect backoff, cancellation cleanup
  - Sync spool drainage (`DrainSpoolBufferUseCase`): batch limit, 2xx pop, 4xx discard, network drop halt
  - Async spool drainage (`AsyncDrainSpoolBufferUseCase`): async drain, 500 status halt, network timeout halt
  - Operational health check (`CheckHealthUseCase`): healthy and unhealthy mapping

## Task 3: Driven Adapters & Mock Transport Fault Injection
- [x] `tests/unit/test_engine_adapters.py`:
  - Sync `HttpxSyncEngineAdapter` with `httpx.MockTransport`
  - Async `HttpxAsyncEngineAdapter` with `httpx.MockTransport`
  - Exception translation: `TimeoutException` $\to$ `TransportTimeoutError`
  - Exception translation: `ConnectError` $\to$ `TransportConnectionError`
  - Exception translation: `HTTPError` $\to$ `TransportError`
  - Clean client closure and connection pool teardown (`close()`, `aclose()`)
- [x] SSE stream engine adapter (`SseStreamEngineAdapter`):
  - Chunked multi-line data buffering
  - Comment line (`:`) and keep-alive ping filtering
  - Custom event type (`event: ...`) and cursor IDs
  - HTTP non-200 responses raising `TransportError`
  - Read timeout and disconnect handling

## Task 4: Driving Adapters & Bootstrap Container Tests
- [x] `tests/unit/test_adapters_and_bootstrap.py`:
  - `Container`: DI container wiring, probe creation, health check use case, CLI health adapter
  - `CliHealthAdapter`: JSON exit codes 0 and 1
  - Client factories: `create_transport_client` and `create_async_transport_client` with injected spool and SQLite storage paths
  - `TokenBucketRateLimiter`: sync and async timeout expirations
  - `SqliteSpoolStorageAdapter` and `MemorySpoolStorageAdapter`: saturation overflow (`reject` vs `drop_oldest`), peek, clear, and close

## Task 5: Verification & Quality Gate Sign-Off
- [x] Run `scripts/verify.py` and verify all checks pass (133 tests passed, 0 lint/type issues)
- [x] Verify global coverage $\ge 95\%$ with `pytest --cov` (96% achieved)
- [x] Zero `ResourceWarning` leaks under `-W error::ResourceWarning`
- [x] Run `./scripts/run_wine_tests.sh` to confirm Windows NT compatibility
