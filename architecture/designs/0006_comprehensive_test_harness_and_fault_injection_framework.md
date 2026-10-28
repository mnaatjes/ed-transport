---
title: "Software Design Document: Comprehensive Test Harness, Fault Injection, and Coverage Governance"
tags: ["testing", "fault-injection", "coverage", "mock-transport", "sqlite-spool", "sdd"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# Software Design Document: Comprehensive Test Harness, Fault Injection, and Coverage Governance

## 1. Introduction and Architectural Traceability

### 1.1 Purpose
This Software Design Document (SDD) articulates the concrete technical design, test topologies, fault injection mechanics, and boundary validation fixtures required to achieve $\ge 95\%$ unit test coverage across the `ed-transport` codebase. It establishes standard test doubles, parameterized test matrices, and deterministic failure scenarios for all ports, use cases, and concrete adapters.

### 1.2 Architectural Traceability Matrix
This design directly realizes the architectural governance and risk mitigation frameworks established across the repository:
* **ADR 0006**: Comprehensive Test Harness, Fault Injection, and Coverage Governance.
* **ADR 0005**: Hexagonal Architecture Implementation Roadmap and Boundary Rules.
* **RISK-11**: Undetected Socket Exhaustion & Connection Leakage under Async Pressure.
* **RISK-12**: Spool Buffer Corruption or Data Loss during Crash/Reboot Cycles.
* **RISK-13**: SSE Stream De-synchronization and Unhandled Stream Termination.
* **Use Cases**:
  * `UC-01`: Resilient Telemetry and Metric Dispatch.
  * `UC-02`: Offline Bounded Request Spooling and FIFO Recovery.
  * `UC-03`: Daemon Server-Sent Events (SSE) IPC Stream Consumption.

---

## 2. Test Suite Topology and Organization

### 2.1 Directory Structure
The test suite is structured to mirror the hexagonal boundaries, separating pure domain invariant tests, interactor use-case tests, concrete adapter tests, and cross-layer integration verification:

```
tests/
├── architecture/
│   └── test_boundaries.py                  # Hexagonal boundary linter & AST invariant verification
├── doubles/
│   ├── __init__.py
│   └── fake_adapters.py                    # In-memory test doubles satisfying DrivenPort SPIs
├── unit/
│   ├── core/
│   │   ├── domain/
│   │   │   ├── test_models.py              # Invariant boundary enforcement (HttpRequest, HttpResponse, etc.)
│   │   │   └── test_retry_policy.py        # Exponential backoff, jitter, retryability checks
│   │   └── use_cases/
│   │       ├── test_execute_request.py     # Sync HTTP dispatch, retries, rate-limiting, error handling
│   │       ├── test_execute_request_async.py # Async HTTP dispatch, cancellation, timeout mappings
│   │       ├── test_consume_stream.py      # SSE stream lifecycle, reconnection, cursor resumption
│   │       ├── test_drain_spool.py         # Sync spool drainage, batch limits, 2xx pop, 4xx discard
│   │       └── test_drain_spool_async.py   # Async spool drainage, backoff on network drop
│   ├── adapters/
│   │   ├── driving/
│   │   │   └── test_transport_client.py    # Facade dispatch, error wrapping, stream exposure
│   │   └── driven/
│   │       ├── test_httpx_engine.py        # HttpxTransportEngine with MockTransport fault injection
│   │       ├── test_sse_stream.py          # HttpxSseStreamEngine parsing, comments, multi-line data
│   │       ├── test_sqlite_spool.py        # SQLiteSpoolStorage concurrency, saturation, corruption
│   │       ├── test_token_bucket.py        # MemoryRateLimiter token replenishment & starvation
│   │       └── test_auth_providers.py      # Bearer, ApiKey, and PreSharedKey header injectors
│   └── bootstrap/
│       └── test_container.py               # Dependency injection container & factory verification
└── conftest.py                             # Shared Pytest fixtures, mock servers, and leak detection
```

---

## 3. Detailed Component Test Specifications

### 3.1 Transport Engine Testing (`test_httpx_engine.py`)

#### 3.1.1 Overview
Tests concrete implementations [`HttpxTransportEngine`](file:///home/michael/src/github.com/mnaatjes/ed-transport/src/ed_transport/adapters/driven/engine/httpx_engine.py) and [`AsyncHttpxTransportEngine`](file:///home/michael/src/github.com/mnaatjes/ed-transport/src/ed_transport/adapters/driven/engine/httpx_engine.py) using `httpx.MockTransport`. No real network sockets are opened.

#### 3.1.2 Test Cases & Fault Injection Scenarios
1. **Happy Path Dispatch (`test_dispatch_sync_success`, `test_dispatch_async_success`):**
   - Validates proper mapping of `HttpRequest` method, URL, headers, and body into outgoing `httpx.Request`.
   - Validates proper reconstruction of `HttpResponse` (status code, headers, byte payload).
2. **Timeout Error Translation (`test_dispatch_timeout_mapping`):**
   - Inject `httpx.TimeoutException` (or `httpx.ReadTimeout`, `httpx.ConnectTimeout`).
   - Asserts engine wraps the error in `TransportTimeoutError` with the original exception chained via `from err`.
3. **Connection Error Translation (`test_dispatch_connection_failure_mapping`):**
   - Inject `httpx.ConnectError` and `httpx.NetworkError`.
   - Asserts engine wraps the error in `TransportConnectionError`.
4. **Generic HTTP Error Translation (`test_dispatch_generic_error_mapping`):**
   - Inject generic `httpx.HTTPError`.
   - Asserts engine wraps the error in `TransportError`.
5. **Client Lifecycle & Cleanup (`test_engine_close_releases_resources`):**
   - Asserts `close()` and `aclose()` methods properly terminate underlying HTTPX client pools and set internal client handles to `None`.

---

### 3.2 SSE Stream Engine Testing (`test_sse_stream.py`)

#### 3.2.1 Overview
Tests [`HttpxSseStreamEngine`](file:///home/michael/src/github.com/mnaatjes/ed-transport/src/ed_transport/adapters/driven/engine/sse_stream.py) using simulated chunked byte generators via `httpx.MockTransport`.

#### 3.2.2 Test Cases & Protocol Boundary Scenarios
1. **Multi-line Event Data Aggregation (`test_sse_multiline_data_chunking`):**
   - Inject stream:
     ```http
     event: telemetry\n
     data: {"part": 1}\n
     data: {"part": 2}\n
     id: evt-100\n
     \n
     ```
   - Asserts parsed `TelemetryEvent.data` concatenates lines with newlines: `"{\"part\": 1}\n{\"part\": 2}"`.
2. **Comment and Keep-Alive Heartbeat Filtering (`test_sse_comment_and_heartbeat_skipped`):**
   - Inject stream:
     ```http
     : keep-alive heartbeat\n
     : another comment\n
     data: {"valid": true}\n
     \n
     ```
   - Asserts comment lines starting with `:` are skipped and never yielded as `TelemetryEvent`.
3. **Custom Event Types and Retry Directives (`test_sse_event_type_and_retry_field`):**
   - Inject stream:
     ```http
     event: ping\n
     retry: 15000\n
     data: pong\n
     \n
     ```
   - Asserts `TelemetryEvent.event_type == "ping"` and retry field is recognized.
4. **Invalid HTTP Status Response Handling (`test_sse_non_200_raises_error`):**
   - Inject HTTP 401 Unauthorized or HTTP 404 Not Found response.
   - Asserts `TransportError` is raised before stream iteration begins.
5. **Stream Disconnect and Timeout Injection (`test_sse_read_timeout_translation`):**
   - Inject `httpx.ReadTimeout` during chunk generation.
   - Asserts `TransportTimeoutError` is raised.

---

### 3.3 Server-Sent Events Consumer Interactor (`test_consume_stream.py`)

#### 3.3.1 Overview
Tests [`ConsumeTelemetryStreamUseCase`](file:///home/michael/src/github.com/mnaatjes/ed-transport/src/ed_transport/core/use_cases/consume_stream.py) for stream resilience, exponential backoff, and cursor tracking.

#### 3.3.2 Test Cases
1. **Continuous Event Consumption (`test_consume_stream_yielding_events`):**
   - Consumes continuous stream from `FakeStreamEngineAdapter`, asserting all events yield cleanly to caller.
2. **Automatic Reconnection with Exponential Backoff (`test_consume_stream_reconnect_backoff`):**
   - Simulate transient network drop on first connection attempt, followed by successful reconnect.
   - Asserts backoff delay is calculated with decorrelated jitter and sleep interactor is invoked.
3. **Cursor Continuity via `Last-Event-ID` (`test_consume_stream_cursor_preservation`):**
   - Stream yields event with `id="cursor-42"` before connection drops.
   - Asserts subsequent reconnect request includes `Last-Event-ID: cursor-42` header.
4. **Maximum Retry Limit and Fatal Error Propagation (`test_consume_stream_max_retries_exceeded`):**
   - Inject persistent failures exceeding `max_reconnect_attempts`.
   - Asserts use case halts and propagates terminal `TransportError`.
5. **Explicit Cancellation and Generator Teardown (`test_consume_stream_cancellation`):**
   - Assert stream break / generator exit cleanly halts loop without unhandled background tasks.

---

### 3.4 Spool Storage Engine (`test_sqlite_spool.py`)

#### 3.4.1 Overview
Tests [`SQLiteSpoolStorage`](file:///home/michael/src/github.com/mnaatjes/ed-transport/src/ed_transport/adapters/driven/spool/sqlite_spool.py) against temporary filesystem databases and in-memory test databases.

#### 3.4.2 Test Cases & Storage Boundary Scenarios
1. **FIFO Enqueue and Dequeue (`test_spool_fifo_ordering`):**
   - Enqueue three items: $A$, $B$, $C$.
   - Peek and dequeue asserting strict FIFO order: $A \to B \to C$.
2. **Capacity Saturation and Overflow Strategy (`test_spool_capacity_overflow`):**
   - Configure `max_capacity_bytes = 2048` and `overflow_strategy = "drop_oldest"`.
   - Enqueue records until threshold is breached.
   - Asserts oldest records are automatically purged to accommodate newer records.
   - Configure `overflow_strategy = "reject"`.
   - Asserts enqueue raises `SpoolStorageError` when saturated.
3. **Database Corruption and Recovery (`test_spool_corrupt_database_handling`):**
   - Write random garbage bytes into the SQLite database file on disk.
   - Instantiate `SQLiteSpoolStorage`.
   - Asserts storage initialization detects malformed header and executes recovery protocol without unhandled crash.
4. **Multi-Threaded Concurrent Ingestion (`test_spool_thread_safety`):**
   - Spawn 10 concurrent threads enqueueing and dequeuing 100 requests each.
   - Asserts SQLite WAL mode and internal mutex locks prevent `sqlite3.OperationalError: database is locked`.

---

### 3.5 Spool Draining Interactor Testing (`test_drain_spool.py`, `test_drain_spool_async.py`)

#### 3.5.1 Overview
Tests [`DrainSpoolBufferUseCase`](file:///home/michael/src/github.com/mnaatjes/ed-transport/src/ed_transport/core/use_cases/drain_spool.py) and [`AsyncDrainSpoolBufferUseCase`](file:///home/michael/src/github.com/mnaatjes/ed-transport/src/ed_transport/core/use_cases/drain_spool.py).

#### 3.5.2 Test Cases
1. **Batch Size Limit Enforcement (`test_drain_batch_size_cap`):**
   - Spool 20 requests. Call `execute(batch_size=5)`.
   - Asserts exactly 5 requests are dequeued and dispatched.
2. **HTTP 2xx Success Ack and Dequeue (`test_drain_success_purges_record`):**
   - Enqueued request receives HTTP 200 or 204.
   - Asserts record is removed from spool storage.
3. **HTTP 4xx Permanent Rejection Discard (`test_drain_client_error_drops_poison_pill`):**
   - Enqueued request receives HTTP 400 Bad Request or HTTP 422 Unprocessable Entity.
   - Asserts poison-pill request is discarded to prevent infinite drain blockage.
4. **HTTP 5xx / Network Failure Halts Drain (`test_drain_server_error_preserves_queue`):**
   - Enqueued request receives HTTP 503 Service Unavailable or network drop.
   - Asserts record remains in spool, drainage loop halts, and subsequent records are not attempted.

---

### 3.6 Domain Models & DTO Invariants (`test_models.py`, `test_retry_policy.py`)

#### 3.6.1 Overview
Validates strict validation constraints on domain entities and value objects:
- `HttpRequest`: URL format, uppercase method, immutable headers mapping, byte payload coercion.
- `HttpResponse`: HTTP status integer range (100–599), binary payload integrity, latency tracking.
- `RetryPolicy`: Jitter bounds ($\ge 0$), exponential multiplier ($\ge 1.0$), maximum backoff caps.
- `RateLimitRule`: Sustained and burst rate positivity, bucket interval validity.

---

## 4. Resource Lifecycle, Mocking, and Teardown Protocols

### 4.1 Zero Resource Leaks
All test cases allocating file descriptors, temporary directories, or async event loops must register explicit teardown hooks:
* Use `pytest-mock` or dependency injection instead of global monkeypatching.
* Temporary databases must be isolated using `tmp_path` fixture.
* All async tests must be marked with `@pytest.mark.asyncio`.
* All engine clients must be closed in `finally` blocks or context managers.

### 4.2 Prohibited Patterns
* **No Real Sockets**: Under no circumstances should tests attempt outbound network connections to external hosts.
* **No Global State**: Tests must not modify global environment variables or global class attributes without guaranteed restoration.

---

## 5. Verification and Acceptance Criteria

1. **Test Execution**:
   - Pytest execution across the entire suite passes 100%: `.venv/bin/pytest`.
   - Architecture boundary linter passes: `.venv/bin/lint-imports`.
   - Windows NT Wine verification script passes: `./scripts/run_wine_tests.sh`.
2. **Coverage Target**:
   - Global statement coverage $\ge 95\%$.
   - Branch coverage $\ge 90\%$.
   - Zero coverage regression across `src/ed_transport/`.
