# Implementation Checklist: Hexagonal Architecture Core and Driven Adapters (ADR-0005 / SDD-005)

## 1. Core Domain Layer (`src/ed_transport/core/domain/`)
- [x] Add `RateLimitRule` value object in `src/ed_transport/core/domain/models.py`
- [x] Add `auto_recover_corrupt: bool = False` to `SpoolConfig` in `src/ed_transport/core/domain/models.py`
- [x] Add `SpoolStorageCorruptError` domain exception in `src/ed_transport/core/domain/exceptions.py`
- [x] Export new domain symbols in `src/ed_transport/core/domain/__init__.py`

## 2. Port Data Transfer Objects (`src/ed_transport/core/ports/dto/`)
- [x] Add immutable `SpoolRecordDTO` in `src/ed_transport/core/ports/dto/transport_dto.py`
- [x] Export `SpoolRecordDTO` in `src/ed_transport/core/ports/dto/__init__.py`

## 3. Driven Secondary SPI Ports (`src/ed_transport/core/ports/driven/`)
- [x] Create `TransportEnginePort` and `AsyncTransportEnginePort` in `src/ed_transport/core/ports/driven/engine_port.py`
- [x] Create `RateLimiterPort` in `src/ed_transport/core/ports/driven/rate_limiter_port.py`
- [x] Create `SpoolStoragePort` in `src/ed_transport/core/ports/driven/spool_storage_port.py`
- [x] Create `StreamEnginePort` in `src/ed_transport/core/ports/driven/stream_engine_port.py`
- [x] Export all driven SPI ports in `src/ed_transport/core/ports/driven/__init__.py`

## 4. Core Use-Case Interactors (`src/ed_transport/core/use_cases/`)
- [x] Implement `ExecuteHttpRequestUseCase` (sync dispatch, rate limiter, jittered retries) in `src/ed_transport/core/use_cases/execute_request.py`
- [x] Implement `AsyncExecuteHttpRequestUseCase` (async dispatch, rate limiter, non-blocking retries) in `src/ed_transport/core/use_cases/execute_request_async.py`
- [x] Implement `DrainSpoolBufferUseCase` and `AsyncDrainSpoolBufferUseCase` (on-demand FIFO drain) in `src/ed_transport/core/use_cases/drain_spool.py`
- [x] Implement `ConsumeTelemetryStreamUseCase` (async generator, jittered reconnects, Last-Event-ID) in `src/ed_transport/core/use_cases/consume_stream.py`
- [x] Export all interactors in `src/ed_transport/core/use_cases/__init__.py`

## 5. Driven Infrastructure Adapters (`src/ed_transport/adapters/driven/`)
- [x] Implement `HttpxSyncEngineAdapter` & `HttpxAsyncEngineAdapter` in `src/ed_transport/adapters/driven/engine/httpx_engine.py`
- [x] Export engine adapters in `src/ed_transport/adapters/driven/engine/__init__.py`
- [x] Implement `TokenBucketRateLimiter` (thread-safe and async) in `src/ed_transport/adapters/driven/rate_limit/token_bucket.py`
- [x] Export rate limiter in `src/ed_transport/adapters/driven/rate_limit/__init__.py`
- [x] Implement `MemorySpoolStorageAdapter` in `src/ed_transport/adapters/driven/spool/memory_spool.py`
- [x] Implement `SqliteSpoolStorageAdapter` (WAL mode, busy timeout, process lock, capacity enforcement) in `src/ed_transport/adapters/driven/spool/sqlite_spool.py`
- [x] Export spool adapters in `src/ed_transport/adapters/driven/spool/__init__.py`
- [x] Implement `SseStreamEngineAdapter` in `src/ed_transport/adapters/driven/stream/sse_stream.py`
- [x] Export stream adapter in `src/ed_transport/adapters/driven/stream/__init__.py`
- [x] Export all driven adapters in `src/ed_transport/adapters/driven/__init__.py`

## 6. Bootstrap Composition Root & Factories (`src/ed_transport/bootstrap/`)
- [x] Implement `create_transport_client` and `create_async_transport_client` in `src/ed_transport/bootstrap/client_factory.py`
- [x] Export client factories in `src/ed_transport/bootstrap/__init__.py` and `src/ed_transport/__init__.py`

## 7. Automated Test Suite
- [x] Unit tests for `ExecuteHttpRequestUseCase` & `AsyncExecuteHttpRequestUseCase` in `tests/unit/test_execute_request_use_case.py`
- [x] Unit tests for `TokenBucketRateLimiter` in `tests/unit/test_token_bucket.py`
- [x] Unit tests for `MemorySpoolStorageAdapter` & `SqliteSpoolStorageAdapter` in `tests/unit/test_spool_adapters.py`
- [x] Unit tests for `create_transport_client` & `create_async_transport_client` in `tests/unit/test_client_factory.py`
- [x] Update architectural boundary tests in `tests/architecture/test_boundaries.py` for new modules and imports

## 8. Diataxis Documentation (`docs/`)
- [x] Update `docs/reference/transport_client.md` with client factories, driven SPIs, and new exceptions
- [x] Create `docs/reference/configuration.md` detailing all configuration value objects
- [x] Update `docs/how-to/spool_offline_requests.md` with SQLite configuration and corruption recovery
- [x] Create `docs/how-to/configure_rate_limits.md` for per-destination rate limits
- [x] Create `docs/how-to/initialize_production_client.md` for one-line client factory usage
- [x] Create `docs/tutorials/quickstart_resilient_dispatch.md` beginner guide
- [x] Create `docs/explanation/offline_spool_architecture.md` deep dive

## 9. Verification Gates
- [x] Run `.venv/bin/python scripts/verify.py` (pre-commit, import-linter, mypy, pytest)
- [x] Run `./scripts/run_wine_tests.sh` (Windows NT simulation)
