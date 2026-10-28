---
title: "ADR 0006: Comprehensive Test Harness, Fault Injection, and Coverage Governance"
status: "accepted"
date: "2026-10-28"
deciders: ["Core Architecture Team"]
consulted: ["ADR 0001", "ADR 0002", "ADR 0004", "ADR 0005", "RISK-11", "RISK-12", "RISK-13", "SDD-005"]
informed: ["All Engineers", "Downstream Consumer Authors (ed-capi, ed-eddn, ed-connectors)"]
tags: ["adr", "testing", "coverage", "fault-injection", "hexagonal", "mock-transport", "sse", "wal"]
---

# ADR 0006: Comprehensive Test Harness, Fault Injection, and Coverage Governance

## Context and Problem Statement

Following the completion of the Hexagonal Architecture Core and Driven Adapters in [ADR 0005](0005_hexagonal_architecture_implementation_roadmap.md), static boundary compliance achieved 100% adherence across all 39 architectural invariants. However, an empirical coverage audit revealed critical behavioral gaps:
1. Overall statement coverage resides at 77% (1,149 statements, 263 missed).
2. Driven infrastructure adapters have significant unexercised blocks:
   * `SseStreamEngineAdapter` (24% coverage): multi-line SSE frames, comments, and connection failures are untested.
   * `HttpxSyncEngineAdapter` and `HttpxAsyncEngineAdapter` (38% coverage): real engine dispatch and exception translation (`httpx.ConnectTimeout` $\rightarrow$ `TransportTimeoutError`) are untested.
3. Complex use cases are under-verified:
   * `DrainSpoolBufferUseCase` & `AsyncDrainSpoolBufferUseCase` (39% coverage): batch boundary limits, non-retriable discard rules, and network drop halts are unexercised.
   * `ConsumeTelemetryStreamUseCase` (42% coverage): exponential backoff, jitter calculation, and `Last-Event-ID` cursor preservation across dropped connections are untested.
   * `AsyncExecuteHttpRequestUseCase` (67% coverage): retries on 429/503 and network disconnects with non-blocking sleep are untested.
4. Edge cases in driven persistence and rate limiters lack robustness:
   * `SqliteSpoolStorageAdapter`: byte capacity ceiling enforcement (`max_capacity_bytes`), overflow strategies (`drop_oldest` vs `reject`), and WAL multi-threaded contention are unexercised. Noticeable unclosed connection warnings occur during test teardown.
   * `TokenBucketRateLimiter`: custom `destination_rules` and time-based refill behaviors are unexercised.

How do we architect an offline, deterministic, and comprehensive test harness that achieves $\ge 95\%$ statement coverage without violating library invariants (zero external daemon dependencies, zero network access, zero unclosed database handles)?

---

## Decision Drivers

* **Zero Live Network Access:** All HTTP dispatch and Server-Sent Events streaming tests must run fully offline using in-memory mock transports (`httpx.MockTransport`) or virtual stream generators.
* **Deterministic Fault Injection:** The harness must deterministically simulate socket timeouts, connection resets, HTTP 429 rate limit backoff signals, 503 service drops, and corrupted database headers.
* **Resource Hygiene & Leak Elimination:** All test fixtures must explicitly close database connections and engine sockets, eliminating Python `ResourceWarning: unclosed database` diagnostics.
* **Hexagonal Test Topology Parity:** Test suites must strictly parallel the hexagonal layers (`tests/unit/core/domain/`, `tests/unit/core/use_cases/`, `tests/unit/adapters/driven/`, `tests/unit/bootstrap/`).
* **Cross-Platform Reproducibility:** All tests must pass under Linux (`.venv/bin/pytest`) and the Windows NT Wine simulation (`./scripts/run_wine_tests.sh`).

---

## Considered Options

1. **Option 1: Rely Strictly on In-Memory Fakes (`tests/doubles/fake_adapters.py`):**
   * *Pros:* Fast, simple, zero external dependencies.
   * *Cons:* Leaves concrete driven adapters (`HttpxSyncEngineAdapter`, `SqliteSpoolStorageAdapter`, `SseStreamEngineAdapter`) completely untested against real engine semantics and exception translation.
2. **Option 2: Spin Up Live Ephemeral HTTP & SSE Servers (`pytest-httpserver` or `uvicorn`):**
   * *Pros:* Tests real socket communication.
   * *Cons:* Introduces subprocess and daemon lifecycle overhead, port collision risks in CI/CD, thread leak risks, and potential violations of Hexagonal zero-lifecycle-pollution rules.
3. **Option 3: Layered Hybrid Harness: In-Memory MockTransports, Fault Injection Doubles, and Direct SQLite Spool Tests (Chosen):**
   * Use `httpx.MockTransport` to simulate synchronous and asynchronous HTTP/SSE network responses, stream chunking, and network errors in-process.
   * Use direct file-based and in-memory SQLite fixtures with explicit teardown hooks to verify WAL concurrency, capacity saturation, and corruption auto-recovery.
   * Exercise use case interactors against both fake doubles and mock adapters.

---

## Decision Outcome

Chosen Option: **Option 3: Layered Hybrid Harness**.

### 1. Test Suite Architecture and Topology

The test directory is organized into four distinct test categories:

```text
tests/
├── architecture/
│   └── test_boundaries.py            # AST boundary compliance & import isolation
├── doubles/
│   ├── fake_adapters.py              # In-memory test doubles satisfying HEXA-TRUTH-27
│   └── fake_system_probe.py          # OS probe test double
└── unit/
    ├── adapters/
    │   ├── test_httpx_engine.py      # HttpxSyncEngineAdapter & HttpxAsyncEngineAdapter via MockTransport
    │   ├── test_sse_stream.py        # SseStreamEngineAdapter line parsing & frame assembly
    │   ├── test_sqlite_spool.py      # SqliteSpoolStorageAdapter WAL, capacity, & corrupt recovery
    │   ├── test_memory_spool.py      # MemorySpoolStorageAdapter circular deque & byte limits
    │   └── test_token_bucket.py      # TokenBucketRateLimiter destination rules & refill timing
    ├── core/
    │   ├── test_domain_models.py     # Domain validation invariants on Config & DTO value objects
    │   ├── test_execute_request.py   # Sync & Async ExecuteHttpRequestUseCase retries & jitter
    │   ├── test_drain_spool.py       # Sync & Async DrainSpoolBufferUseCase batching & pruning
    │   └── test_consume_stream.py    # ConsumeTelemetryStreamUseCase reconnects & Last-Event-ID
    └── bootstrap/
        ├── test_client_factory.py    # create_transport_client & create_async_transport_client
        └── test_container.py         # Container composition root DI wiring
```

---

## Structural Requirements and Fault Injection Specifications

### 1. Mock HTTP Engine Transport (`test_httpx_engine.py`)
* Use `httpx.MockTransport(handler)` to supply deterministic HTTP status codes and headers without network sockets.
* Simulate network exceptions by configuring the handler to raise:
  * `httpx.ConnectTimeout` and `httpx.ReadTimeout` $\rightarrow$ assert adapter translates to `TransportTimeoutError`.
  * `httpx.ConnectError` and `httpx.NetworkError` $\rightarrow$ assert adapter translates to `TransportConnectionError`.
  * Generic `httpx.HTTPError` $\rightarrow$ assert adapter translates to `TransportError`.
* Assert causal chaining is preserved: `err.__cause__` matches the raised `httpx` error.

### 2. SSE Frame Parser Simulation (`test_sse_stream.py`)
* Feed raw byte chunks into `httpx.AsyncClient(transport=httpx.MockTransport(...))`:
  * Multi-line `data:` fields concatenated with `\n`.
  * Custom `event:` type definitions followed by `data:`.
  * Event cursor identifiers via `id:`.
  * Comment lines starting with `:` ignored cleanly.
  * Trailing un-flushed frames yielded upon stream termination.
  * HTTP non-200 responses raising `TransportError`.

### 3. SQLite Concurrency, Capacity, and Resource Hygiene (`test_sqlite_spool.py`)
* **Resource Cleanup:** All database test fixtures must run inside context managers or `try...finally` blocks calling `spool.close()`.
* **Byte Capacity Enforcement:** Verify that when aggregate record size exceeds `max_capacity_bytes`:
  * Under `overflow_strategy="drop_oldest"`, oldest records by `sequence_id` are pruned until new payload fits.
  * Under `overflow_strategy="reject"`, `SpoolCapacityExceededError` is raised and existing records are preserved.
* **Concurrent Multi-Threading:** Spin up 5 concurrent worker threads pushing and popping against a shared `SqliteSpoolStorageAdapter` to verify `threading.RLock` and WAL mode prevent locking errors.

### 4. Telemetry Stream Reconnect and Cursor Recovery (`test_consume_stream.py`)
* Inject an in-memory stream engine double that yields 2 events, raises a simulated `TransportConnectionError`, and yields 2 more events upon reconnect.
* Verify:
  1. `ConsumeTelemetryStreamUseCase` catches the error and executes an exponential backoff sleep.
  2. The reconnect attempt preserves and supplies `Last-Event-ID`.
  3. Clean consumer loop termination when `asyncio.CancelledError` is raised.

### 5. Spool Queue Draining Semantics (`test_drain_spool.py`)
* Verify `DrainSpoolBufferUseCase`:
  * Respects `batch_size` limit (e.g., if 100 items are queued and `batch_size=20`, exactly 20 are drained).
  * On HTTP 2xx: dequeues record.
  * On HTTP 4xx (non-429): dequeues and discards unprocessable payload.
  * On HTTP 5xx or `TransportConnectionError`: halts draining immediately and retains current record in storage.

### 6. Domain Model and DTO Self-Validation (`test_domain_models.py`)
* Verify `DomainValidationError` is raised when:
  * `RateLimitConfig(requests_per_second<=0)` or `burst_capacity<=0`.
  * `RetryConfig(max_retries<0)` or `base_delay<=0` or `max_backoff < base_delay`.
  * `SpoolConfig(max_capacity<=0)` or `memory_limit_bytes<=0` or invalid `eviction_policy`.
  * `HttpRequestDTO` contains invalid schemes or unsupported HTTP methods.
  * `HttpResponseDTO` contains out-of-range status codes (`<100` or `>599`).

---

## Quality Gate Compliance

All test additions must adhere to:
1. **Target Coverage:** Minimum 95% statement coverage across `src/ed_transport`.
2. **Quality Verification:** Passing `.venv/bin/python scripts/verify.py` (pre-commit, import-linter, mypy, pytest).
3. **Wine Simulation:** Passing `./scripts/run_wine_tests.sh` under Windows NT.
