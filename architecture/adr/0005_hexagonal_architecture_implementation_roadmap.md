---
title: "ADR 0005: Hexagonal Architecture Component Inventory and Implementation Roadmap"
status: "accepted"
date: "2026-10-28"
deciders: ["Core Architecture Team"]
consulted: ["ADR 0001", "ADR 0002", "ADR 0003", "ADR 0004", "UC-01", "UC-02", "UC-03", "UC-04", "SDD-002"]
informed: ["All Engineers", "Downstream Consumer Authors (ed-capi, ed-eddn, ed-connectors, ed-telemetry)"]
tags: ["adr", "architecture", "hexagonal", "roadmap", "components", "ports", "adapters", "use-cases"]
---

# ADR 0005: Hexagonal Architecture Component Inventory and Implementation Roadmap

## Context and Problem Statement

In [ADR 0002](0002_driving_adapter_facade_definition.md) and [SDD-002](0002_transport_client_driving_facade_architecture.md), `ed-transport` established its driving adapter perimeter: the `TransportClient` and `AsyncTransportClient` facades. These facades delegate strictly to driving port contracts (`TransportPort`, `AsyncTransportPort`, `SpoolManagerPort`, `TelemetryStreamPort`).

While the driving perimeter and facade surfaces are fully implemented, the interior of the hexagon currently contains stub or mock targets. To deliver actual network dispatch, rate limiting, retries with jitter, offline request buffering, and local daemon telemetry streaming, we must systematically design and implement the internal hexagonal components.

What is the complete, comprehensive inventory of domain entities, driven secondary SPI ports, use-case interactors, driven adapters, and bootstrap composition factories required to make `TransportClient` fully operational?

---

## Decision Drivers

* **Outside-In Hexagonal Completion:** Every internal component must directly satisfy the driving ports consumed by `TransportClient` and `AsyncTransportClient`.
* **Zero Infrastructure Leakage:** Driven adapters encapsulate network engines (`httpx`, `urllib3`), storage engines (`sqlite3`), and OS primitives without leaking types across port boundaries.
* **Payload Agnosticism (`UC-04`, `RISK-10`):** Pure byte/string handling across all layers; zero coupling to game schemas or `ed-models`.
* **Concurrency Safety (`RISK-07`):** Explicit separation of synchronous and asynchronous interactors and adapters to prevent event-loop deadlocks.

---

## Decision Outcome

Chosen Option: **Implement a 5-tier Hexagonal Component Inventory with Outside-In Delivery Milestones**.

```text
======================================================================================================
1. DRIVING ADAPTERS (As-Built)
   src/ed_transport/adapters/driving/
   ├── TransportClient           (Synchronous entrypoint)
   └── AsyncTransportClient      (Asynchronous entrypoint)
======================================================================================================
                                    │
                                    ▼ (delegates to)
======================================================================================================
2. DRIVING PORTS (As-Built)
   src/ed_transport/core/ports/driving/
   ├── TransportPort             (send: HttpRequestDTO -> HttpResponseDTO)
   ├── AsyncTransportPort        (send_async: HttpRequestDTO -> HttpResponseDTO)
   ├── SpoolManagerPort          (enqueue, drain, depth, purge)
   └── TelemetryStreamPort       (open_stream: endpoint, topic -> AsyncIterator[RawStreamEventDTO])
======================================================================================================
                                    │
                                    ▼ (implemented by)
======================================================================================================
3. CORE USE-CASE INTERACTORS (To Build)
   src/ed_transport/core/use_cases/
   ├── ExecuteHttpRequestUseCase       (Sync dispatch, rate-limiting, retry loop with jitter)
   ├── AsyncExecuteHttpRequestUseCase  (Async dispatch, token bucket rate-limiting, async retries)
   ├── DrainSpoolBufferUseCase         (Sync FIFO dequeue & dispatch with retry)
   ├── AsyncDrainSpoolBufferUseCase    (Async FIFO dequeue & dispatch)
   └── ConsumeTelemetryStreamUseCase   (SSE reconnection loop, backpressure, event parser)
======================================================================================================
        │                                                           │
        ▼ (utilizes)                                                ▼ (invokes via SPI)
┌─────────────────────────────────┐       ┌──────────────────────────────────────────────────────────┐
│ CORE DOMAIN LAYER (To Expand)   │       │ 4. DRIVEN SECONDARY SPI PORTS (To Build)                 │
│ src/ed_transport/core/domain/   │       │ src/ed_transport/core/ports/driven/                      │
│ ├── models.py                   │       │ ├── HttpEnginePort        (Raw socket sync dispatch)     │
│ │   ├── RateLimitConfig         │       │ ├── AsyncHttpEnginePort   (Raw socket async dispatch)    │
│ │   ├── RetryConfig             │       │ ├── RateLimiterPort       (Acquire token, check quota)   │
│ │   ├── SpoolConfig             │       │ ├── SpoolStoragePort      (push, pop, peek, count, size) │
│ │   └── SpoolRecord (New)       │       │ └── StreamEnginePort      (Raw chunked SSE byte stream)  │
│ └── exceptions.py (DomainError) │       └──────────────────────────────────────────────────────────┘
└─────────────────────────────────┘                                 │
                                                                    ▼ (implemented by)
======================================================================================================
5. DRIVEN INFRASTRUCTURE ADAPTERS (To Build)
   src/ed_transport/adapters/driven/
   ├── engine/
   │   ├── HttpxSyncEngineAdapter     (implements HttpEnginePort)
   │   └── HttpxAsyncEngineAdapter    (implements AsyncHttpEnginePort)
   ├── rate_limit/
   │   └── TokenBucketRateLimiter     (implements RateLimiterPort; thread-safe and async buckets)
   ├── spool/
   │   ├── SqliteSpoolStorageAdapter  (implements SpoolStoragePort; persistent disk FIFO buffer)
   │   └── MemorySpoolStorageAdapter  (implements SpoolStoragePort; in-memory circular deque)
   └── stream/
       └── SseStreamEngineAdapter     (implements StreamEnginePort; chunked SSE line parser)
======================================================================================================
                                    │
                                    ▼ (wired together by)
======================================================================================================
6. BOOTSTRAP COMPOSITION ROOT & FACTORIES (To Expand)
   src/ed_transport/bootstrap/
   ├── container.py                   (Dependency Injection Wiring)
   └── client_factory.py              (create_transport_client & create_async_transport_client)
======================================================================================================
```

---

## Detailed Component Inventory

### 1. Core Domain Layer (`src/ed_transport/core/domain/`)

* **Existing Components:**
  * `exceptions.py`: `DomainError`, `TransportError`, `TransportTimeoutError`, `TransportConnectionError`, `RateLimitExceededError`, `MaxRetriesExceededError`, `SpoolCapacityExceededError`, `InvalidPayloadTypeError`.
  * `models.py`: `RateLimitConfig`, `RetryConfig`, `SpoolConfig`.
* **New Components to Build:**
  * `SpoolRecord`: Immutable domain entity representing a persisted offline request with serial number, timestamp, retry count, and serialized `HttpRequestDTO`.
  * `RateLimitRule`: Value object defining destination endpoint patterns and token bucket replenishment rates.

---

### 2. Driven Secondary SPI Ports (`src/ed_transport/core/ports/driven/`)

All secondary ports must be abstract (`abc.ABC` or `@runtime_checkable Protocol`) and live under `core/ports/driven/`:

1. **`HttpEnginePort` (`http_engine_port.py`):**
   * Synchronous SPI for raw network transmission.
   * `send(request: HttpRequestDTO) -> HttpResponseDTO`
   * `close() -> None`
2. **`AsyncHttpEnginePort` (`async_http_engine_port.py`):**
   * Asynchronous SPI for raw network transmission.
   * `async send_async(request: HttpRequestDTO) -> HttpResponseDTO`
   * `async aclose() -> None`
3. **`RateLimiterPort` (`rate_limiter_port.py`):**
   * SPI for rate-limiting enforcement.
   * `acquire(destination: str, timeout: float | None = None) -> bool`
   * `async acquire_async(destination: str, timeout: float | None = None) -> bool`
4. **`SpoolStoragePort` (`spool_storage_port.py`):**
   * SPI for offline request queue persistence.
   * `push(record: SpoolRecord) -> None`
   * `pop() -> SpoolRecord | None`
   * `peek() -> SpoolRecord | None`
   * `count() -> int`
   * `size_bytes() -> int`
   * `clear() -> None`
5. **`StreamEnginePort` (`stream_engine_port.py`):**
   * Asynchronous SPI for reading chunked SSE network streams.
   * `open_stream(endpoint: str, topic: str) -> AsyncIterator[RawStreamEventDTO]`

---

### 3. Core Use-Case Interactors (`src/ed_transport/core/use_cases/`)

Stateless interactors orchestrating business logic and implementing driving ports:

1. **`ExecuteHttpRequestUseCase` (`execute_request.py`):**
   * Implements `TransportPort`.
   * Injects: `HttpEnginePort`, `RateLimiterPort`, `RetryConfig`, `RateLimitConfig`.
   * Enforces token bucket rate limits, handles jittered retries on 429/503/network drops, and preserves diagnostic causal traces.
2. **`AsyncExecuteHttpRequestUseCase` (`execute_request_async.py`):**
   * Implements `AsyncTransportPort`.
   * Native `asyncio` implementation with non-blocking sleep and async engine dispatch.
3. **`DrainSpoolBufferUseCase` (`drain_spool.py`):**
   * Implements `SpoolManagerPort`.
   * Injects: `SpoolStoragePort`, `TransportPort`.
   * Dequeues records in FIFO order, dispatches them through the transport interactor, and prunes on success.
4. **`AsyncDrainSpoolBufferUseCase` (`drain_spool_async.py`):**
   * Asynchronous variant implementing `SpoolManagerPort` using `AsyncTransportPort`.
5. **`ConsumeTelemetryStreamUseCase` (`consume_stream.py`):**
   * Implements `TelemetryStreamPort`.
   * Injects: `StreamEnginePort`.
   * Manages reconnection exponential backoff, monotonic event IDs, and yields clean `RawStreamEventDTO` records.

---

### 4. Driven Infrastructure Adapters (`src/ed_transport/adapters/driven/`)

Concrete implementations of secondary SPIs:

1. **HTTP Engines (`adapters/driven/engine/`):**
   * `HttpxSyncEngineAdapter`: Implements `HttpEnginePort` using `httpx.Client`. Maps engine exceptions to `DomainError` subclasses.
   * `HttpxAsyncEngineAdapter`: Implements `AsyncHttpEnginePort` using `httpx.AsyncClient`.
2. **Rate Limiting (`adapters/driven/rate_limit/`):**
   * `TokenBucketRateLimiter`: Thread-safe synchronous token bucket implementation.
   * `AsyncTokenBucketRateLimiter`: Asyncio lock-guarded token bucket.
3. **Spool Storage (`adapters/driven/spool/`):**
   * `SqliteSpoolStorageAdapter`: Production disk-persisted circular FIFO queue using SQLite in WAL mode. Respects `SpoolConfig.storage_path` and `max_capacity_bytes`.
   * `MemorySpoolStorageAdapter`: Fast in-memory deque adapter for unit tests and non-persisted buffering.
4. **Streaming (`adapters/driven/stream/`):**
   * `SseStreamEngineAdapter`: Implements `StreamEnginePort` over chunked HTTP responses, parsing SSE lines (`event:`, `data:`, `id:`).

---

### 5. Bootstrap Composition Root & Factories (`src/ed_transport/bootstrap/`)

1. **`Container` (`container.py`):**
   * Wires concrete adapters to interactors based on configuration.
2. **`ClientFactory` (`client_factory.py`):**
   * `create_transport_client(...) -> TransportClient`: Instant, production-ready synchronous client wired with HTTP engine, token bucket, and SQLite spool storage.
   * `create_async_transport_client(...) -> AsyncTransportClient`: Production-ready asynchronous client wired with async HTTP engine, async rate limiter, and telemetry stream engine.

---

## Implementation Roadmap

The components will be delivered in 4 sequential, independently testable phases:

* **Phase 1: HTTP Execution Engine & Rate Limiter**
  * Core: `HttpEnginePort`, `AsyncHttpEnginePort`, `RateLimiterPort`.
  * Adapters: `HttpxSyncEngineAdapter`, `HttpxAsyncEngineAdapter`, `TokenBucketRateLimiter`.
  * Use Cases: `ExecuteHttpRequestUseCase`, `AsyncExecuteHttpRequestUseCase`.
  * Deliverable: Basic `client.get()` and `client.post()` make real HTTP requests with retries and rate limits.
* **Phase 2: Offline Spooling Subsystem**
  * Core: `SpoolRecord`, `SpoolStoragePort`.
  * Adapters: `SqliteSpoolStorageAdapter`, `MemorySpoolStorageAdapter`.
  * Use Cases: `DrainSpoolBufferUseCase`, `AsyncDrainSpoolBufferUseCase`.
  * Deliverable: `client.send_buffered()` and `client.drain_spool()` persist offline requests to disk.
* **Phase 3: Telemetry Streaming Engine**
  * Core: `StreamEnginePort`.
  * Adapters: `SseStreamEngineAdapter`.
  * Use Cases: `ConsumeTelemetryStreamUseCase`.
  * Deliverable: `async_client.open_stream()` consumes live SSE events from local daemons.
* **Phase 4: Composition Root & Production Factories**
  * Bootstrap: `create_transport_client()`, `create_async_transport_client()`.
  * Deliverable: Downstream apps (`ed-capi`, `ed-eddn`) can instantiate fully wired clients in a single line.

---

## Consequences

### Positive
* Complete roadmap provides clear, isolated implementation targets without architectural ambiguity.
* Every component strictly respects Hexagonal Architecture invariants and passes automated AST quality gates.
* Phase separation allows incremental delivery with full unit and contract test coverage at each step.

### Expected Maintenance Costs (Design Trade-offs)
* Dual sync/async paths require maintaining parallel interactors and engine adapters.
* SQLite spooling requires database schema migration handling and file lock management across Windows and Linux.
