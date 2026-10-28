---
title: "ADR 0002: Driving Adapter Facade Definition and API Surface"
status: "accepted"
date: "2026-10-28"
deciders: ["Core Architecture Team"]
consulted: ["ADR 0001", "ADR 0035 (ed-telemetry)", "UC-01", "UC-02", "UC-03", "UC-04", "RISK-01", "RISK-02", "RISK-03", "RISK-05", "RISK-07", "RISK-08", "RISK-10"]
informed: ["All Engineers", "Downstream Consumer Authors (ed-capi, ed-eddn, ed-connectors, ed-state)"]
tags: ["adr", "architecture", "facade", "driving-adapter", "api-surface", "hexagonal", "ports", "async-sync"]
---

# ADR 0002: Driving Adapter Facade Definition and API Surface

## Context and Problem Statement

`ed-transport` is architected as an internal shared library rather than a standalone daemon with an HTTP server or CLI entrypoint. In classical Hexagonal Architecture, driving (primary) adapters initiate interactions with the hexagon (e.g. web controllers, message bus consumers, CLI commands). Because `ed-transport` is consumed as a Python dependency by other packages (`ed-capi`, `ed-eddn`, `ed-connectors`, `ed-state`), downstream developers require a programmatic entrypoint.

Without a well-defined driving adapter layer:
1. Downstream consumers would be forced to interact directly with internal use-case interactors (`ExecuteHttpRequestUseCase`, `ConsumeTelemetryStreamUseCase`, `DrainSpoolBufferUseCase`), manually wiring dependencies, rate limiters, token buckets, and credential providers.
2. The internal use-case layout would become the de facto public API, preventing internal refactoring and violating the Dependency Inversion Principle.
3. Consumers operating in mixed execution contexts (asynchronous event loops vs synchronous worker threads) could trigger event loop deadlocks (`RISK-07`) if transport execution semantics are ambiguous.
4. Consumers might attempt to pass domain event objects or schemas directly into internal methods, violating payload agnosticism (`UC-04`, `RISK-10`).

How should `ed-transport` structure and expose its driving adapter perimeter to satisfy the use-case requirements of `UC-01` through `UC-04` while preserving strict hexagonal boundaries?

---

## Decision Drivers

* **Consumer Developer Experience (DX):** Provide an intuitive, modern client interface (`client.get()`, `client.post()`, `client.open_stream()`) that hides internal wiring complexity from `ed-capi`, `ed-eddn`, and `ed-connectors`.
* **Outside-In Boundary Preservation:** The facade must be a pure Driving Adapter located in `adapters/driving/`, implementing and delegating strictly to driving port contracts (`core/ports/driving/`).
* **Concurrency Safety (`RISK-07`):** Explicitly support both synchronous applications (`TransportClient`) and asynchronous reactive runtimes (`AsyncTransportClient`) with clean context manager lifecycles (`__enter__` / `__exit__`, `__aenter__` / `__aexit__`), prohibiting blocking `asyncio.run()` calls inside active event loops.
* **Exhaustive Use-Case Coverage:** The facade surface must directly fulfill all operational goals in `UC-01` (Resilient HTTP), `UC-02` (Offline Spooling), `UC-03` (Daemon SSE IPC), and `UC-04` (Domain Model Isolation).

---

## Considered Options

* **Option 1: Direct Use-Case Exposure (No Facade).** Expose `ExecuteHttpRequestUseCase` directly as the public interface, requiring consumers to instantiate use cases and assemble DTOs manually. *(Rejected: Poor developer ergonomics; leaks hexagonal internals to downstream libraries; high friction for common operations like `client.get()`)*.
* **Option 2: Single Synchronous Facade with Internal Event-Loop Wrangling.** Provide a single synchronous class that executes async routines internally using `asyncio.run()`. *(Rejected: Severe risk of `RuntimeError: This event loop is already running` in async environments like `ed-telemetry` or modern GUI/TUI frameworks, violating `RISK-07`)*.
* **Option 3: Dual Ergonomic Driving Facades (`TransportClient` & `AsyncTransportClient`) Backed by Driving Ports.** Implement two specialized driving adapter facades in `adapters/driving/client.py`:
  * `AsyncTransportClient`: Native `async`/`await` interface for asynchronous consumers.
  * `TransportClient`: Thread-safe, synchronous blocking facade delegating to sync engine adapters or isolated thread workers.
  * Both facades wrap driving ports (`HttpTransportPort`, `SpoolManagerPort`, `TelemetryStreamPort`) and expose high-level ergonomic HTTP methods while accepting opaque payloads.

---

## Decision Outcome

Chosen Option: **Option 3: Dual Ergonomic Driving Facades (`TransportClient` & `AsyncTransportClient`) Backed by Driving Ports**.

### 1. Architectural Position in Hexagonal Topology

```text
+----------------------------------------------------------------------------------------------------+
| CONSUMER PLANE: ed-capi / ed-eddn / ed-connectors / ed-state                                       |
|                                                                                                    |
|   client = create_transport_client(...)  OR  async_client = create_async_transport_client(...)      |
|   response = client.get("https://inara.cz/api/v2", ...)                                            |
+----------------------------------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------------------------------+
| DRIVING ADAPTER PLANE: src/ed_transport/adapters/driving/client.py                                 |
|                                                                                                    |
|  class TransportClient / class AsyncTransportClient                                                |
|  * Parameter translation (kwargs -> frozen HttpRequestDTO)                                         |
|  * Ergonomic verb dispatch: get(), post(), put(), delete(), send()                                  |
|  * Spool buffer operations: send_buffered(), drain_spool(), spool_depth                            |
|  * Streaming operations: open_stream()                                                             |
|  * Context manager lifecycle: __enter__/__exit__, __aenter__/__aexit__                             |
+----------------------------------------------------------------------------------------------------+
                                      |
                                      v (implements / delegates to)
+----------------------------------------------------------------------------------------------------+
| DRIVING PORTS PLANE: src/ed_transport/core/ports/driving/                                          |
|                                                                                                    |
|  * HttpTransportPort: send(request: HttpRequestDTO) -> HttpResponseDTO                             |
|  * AsyncHttpTransportPort: send_async(request: HttpRequestDTO) -> HttpResponseDTO                  |
|  * SpoolManagerPort: enqueue(req), drain(), depth()                                                |
|  * TelemetryStreamPort: open_stream(endpoint, topic) -> AsyncIterator[RawStreamEvent]              |
+----------------------------------------------------------------------------------------------------+
                                      |
                                      v
+----------------------------------------------------------------------------------------------------+
| USE CASES PLANE: src/ed_transport/core/use_cases/                                                  |
|  ExecuteHttpRequestUseCase / DrainSpoolBufferUseCase / ConsumeTelemetryStreamUseCase               |
+----------------------------------------------------------------------------------------------------+
```

---

## Exhaustive Use-Case Facade Mapping

The table below maps every operational capability defined across `UC-01` through `UC-04` directly to the methods, properties, and signatures of the driving facade:

| Use Case | Capability / Requirement | Facade Method / Property | Method Signature & Parameter Types | Return Type |
| :--- | :--- | :--- | :--- | :--- |
| **UC-01** | Core Request Dispatch | `send` / `send_async` | `(request: HttpRequestDTO) -> HttpResponseDTO` | `HttpResponseDTO` |
| **UC-01** | Ergonomic GET Dispatch | `get` / `get_async` | `(url: str, *, headers: Mapping[str, str] \| None = None, params: Mapping[str, str] \| None = None, timeout: float \| None = None) -> HttpResponseDTO` | `HttpResponseDTO` |
| **UC-01** | Ergonomic POST Dispatch | `post` / `post_async` | `(url: str, *, body: bytes \| str \| None = None, headers: Mapping[str, str] \| None = None, params: Mapping[str, str] \| None = None, timeout: float \| None = None) -> HttpResponseDTO` | `HttpResponseDTO` |
| **UC-01** | Ergonomic PUT Dispatch | `put` / `put_async` | `(url: str, *, body: bytes \| str \| None = None, headers: Mapping[str, str] \| None = None, params: Mapping[str, str] \| None = None, timeout: float \| None = None) -> HttpResponseDTO` | `HttpResponseDTO` |
| **UC-01** | Ergonomic DELETE Dispatch| `delete` / `delete_async` | `(url: str, *, headers: Mapping[str, str] \| None = None, params: Mapping[str, str] \| None = None, timeout: float \| None = None) -> HttpResponseDTO` | `HttpResponseDTO` |
| **UC-01** | Throttling / Rate Limits | Configured at Init | `RateLimitConfig(requests_per_second: float, burst_capacity: int, destination_key: str)` | Applied per dispatch |
| **UC-01** | Retries & Jitter | Configured at Init | `RetryConfig(max_retries: int, base_delay: float, max_backoff: float, retryable_statuses: frozenset[int])` | Applied per dispatch |
| **UC-01** | Credential Resolution | Configured at Init | Injected via `CredentialProviderPort` (Bearer token, Pre-shared API Key) | Headers injected |
| **UC-02** | Bounded Spool Submission | `send_buffered` / `send_buffered_async` | `(request: HttpRequestDTO \| None = None, *, url: str \| None = None, method: str = "POST", body: bytes \| str \| None = None, headers: Mapping[str, str] \| None = None) -> bool` | `bool` (`True` if dispatched or safely queued) |
| **UC-02** | Manual / Automated Drain | `drain_spool` / `drain_spool_async` | `(batch_size: int = 50) -> int` | `int` (count of successfully drained requests) |
| **UC-02** | Queue Inspection | `spool_depth` (property) | `client.spool_depth` | `int` (active enqueued count) |
| **UC-03** | Persistent SSE Stream | `open_stream` | `(endpoint: str = "/api/v1/stream", topic: str \| None = None) -> AsyncIterator[RawStreamEvent]` | `AsyncIterator[RawStreamEvent]` |
| **UC-03** | Watchdog Health Status | `is_stream_alive` (property) | `client.is_stream_alive` | `bool` |
| **UC-04** | Domain Model Isolation | Type annotations | `body: bytes \| str \| AsyncIterable[bytes]`. Zero imports of `ed_models`. | Raw bytes/strings |
| **Lifecycle**| Resource Disposal | `close` / `aclose` | `client.close()` / `await async_client.aclose()` or context managers | `None` |

---

## Consequences

### Positive
* **Intuitive Downstream DX:** `ed-capi` and `ed-eddn` consume standard methods (`client.post(url, body=data)`) without assembling domain interactors or configuration trees.
* **Strict Decoupling:** The facade acts as an insulating shield. Internal use cases can be refactored, optimized, or split without changing consumer code.
* **Zero Event-Loop Hazards:** Consumers explicitly choose synchronous (`TransportClient`) or asynchronous (`AsyncTransportClient`) facades, eliminating hidden `asyncio.run()` deadlocks (`RISK-07`).
* **Boundary Enforcement Integrity:** All arguments are mapped directly to immutable, frozen DTOs (`HttpRequestDTO`), and payloads remain opaque `bytes`/`str` (`UC-04`).

### Negative / Trade-offs
* **Maintenance of Dual Surface:** Maintaining both synchronous and asynchronous facades requires rigorous test parity across both interfaces.
* **Factory Requirement:** Consumers should initialize clients via the composition root (`create_transport_client`) rather than calling raw class constructors.
