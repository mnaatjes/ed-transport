---
title: "TransportClient and AsyncTransportClient API Reference"
tags: ["transport-client", "facade", "reference", "api", "driving-adapter"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# TransportClient and AsyncTransportClient API Reference

This reference details the public interface, configuration objects, data transfer objects (DTOs), and domain exceptions for the driving adapter facades `TransportClient` and `AsyncTransportClient` in `ed_transport.adapters.driving`.

---

## 1. Module Exports

```python
from ed_transport.adapters.driving import (
    AsyncTransportClient,
    TransportClient,
)
from ed_transport.core.domain.exceptions import (
    InvalidPayloadTypeError,
    MaxRetriesExceededError,
    RateLimitExceededError,
    SpoolCapacityExceededError,
    TransportConnectionError,
    TransportError,
    TransportTimeoutError,
)
from ed_transport.core.domain.models import (
    RateLimitConfig,
    RetryConfig,
    SpoolConfig,
)
from ed_transport.core.ports.dto import (
    HttpRequestDTO,
    HttpResponseDTO,
    RawStreamEventDTO,
)
```

---

## 2. Facade Classes

### `TransportClient`

Synchronous driving adapter facade providing blocking HTTP dispatch, offline request spooling, and lifecycle management.

```python
class TransportClient:
    def __init__(
        self,
        transport_port: TransportPort | None = None,
        spool_port: SpoolManagerPort | None = None,
        rate_limit_config: RateLimitConfig | None = None,
        retry_config: RetryConfig | None = None,
        spool_config: SpoolConfig | None = None,
        default_timeout: float = 30.0,
    ) -> None: ...
```

#### Properties
* `is_closed -> bool`: Indicates whether `close()` has been executed.
* `spool_depth -> int`: Current count of requests enqueued in the spool buffer (returns `0` if no spool port is wired).
* `rate_limit_config -> RateLimitConfig`: Active rate-limiting policy.
* `retry_config -> RetryConfig`: Active retry and jitter parameters.
* `spool_config -> SpoolConfig`: Active offline spooling limits and behavior.
* `default_timeout -> float`: Default per-request timeout in seconds.

#### Methods

* `close() -> None`: Releases client resources and marks the client as closed.
* `__enter__() -> TransportClient`: Enters the runtime context manager.
* `__exit__(exc_type, exc_val, exc_tb) -> None`: Closes the client upon exiting the context.
* `get(url: str, *, headers: Mapping[str, str] | None = None, params: Mapping[str, str] | None = None, timeout: float | None = None) -> HttpResponseDTO`: Sends a synchronous `GET` request.
* `post(url: str, *, body: bytes | str | None = None, headers: Mapping[str, str] | None = None, params: Mapping[str, str] | None = None, timeout: float | None = None) -> HttpResponseDTO`: Sends a synchronous `POST` request.
* `put(url: str, *, body: bytes | str | None = None, headers: Mapping[str, str] | None = None, params: Mapping[str, str] | None = None, timeout: float | None = None) -> HttpResponseDTO`: Sends a synchronous `PUT` request.
* `delete(url: str, *, headers: Mapping[str, str] | None = None, params: Mapping[str, str] | None = None, timeout: float | None = None) -> HttpResponseDTO`: Sends a synchronous `DELETE` request.
* `send(request: HttpRequestDTO) -> HttpResponseDTO`: Dispatches an immutable `HttpRequestDTO` directly through the wired transport port.
* `send_buffered(url: str, *, method: str = "POST", body: bytes | str | None = None, headers: Mapping[str, str] | None = None, params: Mapping[str, str] | None = None, timeout: float | None = None) -> bool`: Attempts immediate dispatch; enqueues the request into the spool buffer if connectivity fails. Returns `True` if dispatched or enqueued, or `False` if discarded or unhandled.
* `drain_spool() -> int`: Flushes buffered requests through the transport port. Returns the number of requests successfully dispatched.

---

### `AsyncTransportClient`

Asynchronous driving adapter facade providing coroutine-based HTTP dispatch, Server-Sent Events (SSE) telemetry streaming, and asynchronous context management.

```python
class AsyncTransportClient:
    def __init__(
        self,
        transport_port: AsyncTransportPort | None = None,
        spool_port: SpoolManagerPort | None = None,
        stream_port: TelemetryStreamPort | None = None,
        rate_limit_config: RateLimitConfig | None = None,
        retry_config: RetryConfig | None = None,
        spool_config: SpoolConfig | None = None,
        default_timeout: float = 30.0,
    ) -> None: ...
```

#### Properties
* `is_closed -> bool`: Indicates whether `aclose()` has been executed.
* `spool_depth -> int`: Current count of requests enqueued in the spool buffer.
* `rate_limit_config -> RateLimitConfig`: Active rate-limiting policy.
* `retry_config -> RetryConfig`: Active retry parameters.
* `spool_config -> SpoolConfig`: Active spool configuration.
* `default_timeout -> float`: Default request timeout in seconds.

#### Methods

* `async aclose() -> None`: Asynchronously releases underlying network connections and resources.
* `async __aenter__() -> AsyncTransportClient`: Enters asynchronous runtime context.
* `async __aexit__(exc_type, exc_val, exc_tb) -> None`: Closes the client upon exiting context.
* `async get(url: str, *, headers: Mapping[str, str] | None = None, params: Mapping[str, str] | None = None, timeout: float | None = None) -> HttpResponseDTO`: Asynchronous `GET` dispatch.
* `async post(url: str, *, body: bytes | str | None = None, headers: Mapping[str, str] | None = None, params: Mapping[str, str] | None = None, timeout: float | None = None) -> HttpResponseDTO`: Asynchronous `POST` dispatch.
* `async put(url: str, *, body: bytes | str | None = None, headers: Mapping[str, str] | None = None, params: Mapping[str, str] | None = None, timeout: float | None = None) -> HttpResponseDTO`: Asynchronous `PUT` dispatch.
* `async delete(url: str, *, headers: Mapping[str, str] | None = None, params: Mapping[str, str] | None = None, timeout: float | None = None) -> HttpResponseDTO`: Asynchronous `DELETE` dispatch.
* `async send(request: HttpRequestDTO) -> HttpResponseDTO`: Dispatches an immutable `HttpRequestDTO` through the asynchronous transport port.
* `async send_buffered(...) -> bool`: Asynchronously attempts dispatch with spool fallback.
* `async drain_spool() -> int`: Asynchronously drains buffered requests from the spool buffer.
* `open_stream(endpoint: str, topic: str) -> AsyncIterator[RawStreamEventDTO]`: Establishes an asynchronous telemetry stream (e.g. SSE) returning raw event DTOs.

---

## 3. Configuration Models

Configuration models are immutable frozen value objects residing in `ed_transport.core.domain.models`.

### `RateLimitConfig`

```python
@dataclass(frozen=True)
class RateLimitConfig:
    rate: float = 10.0
    capacity: int = 10
    time_window_seconds: float = 1.0
    destination: str = "default"
```

* `rate`: Maximum allowed requests per unit window.
* `capacity`: Maximum token bucket burst capacity.
* `time_window_seconds`: Evaluation window period in seconds.
* `destination`: Destination identifier for per-endpoint rate partitioning.

### `RetryConfig`

```python
@dataclass(frozen=True)
class RetryConfig:
    max_retries: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 60.0
    jitter_factor: float = 0.5
```

* `max_retries`: Maximum consecutive retry attempts.
* `base_delay_seconds`: Initial exponential backoff delay.
* `max_delay_seconds`: Ceiling clamp for backoff duration.
* `jitter_factor`: Randomized decorrelated jitter coefficient ($0.0 \le \text{jitter} \le 1.0$).

### `SpoolConfig`

```python
@dataclass(frozen=True)
class SpoolConfig:
    max_capacity_bytes: int = 50 * 1024 * 1024  # 50 MB
    storage_path: str = ""
    overflow_strategy: str = "drop_oldest"
```

* `max_capacity_bytes`: Storage threshold ceiling.
* `storage_path`: Filesystem directory for persistent offline buffering.
* `overflow_strategy`: Buffer behavior on capacity saturation (`drop_oldest` or `reject`).

---

## 4. Data Transfer Objects (DTOs)

Immutable transfer records residing in `ed_transport.core.ports.dto`.

### `HttpRequestDTO`

```python
@dataclass(frozen=True)
class HttpRequestDTO(DataTransferObject):
    url: str
    method: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""
    timeout: float = 30.0
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
```

### `HttpResponseDTO`

```python
@dataclass(frozen=True)
class HttpResponseDTO(DataTransferObject):
    status_code: int
    headers: Mapping[str, str]
    body: bytes
    request_correlation_id: str = ""

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")
```

### `RawStreamEventDTO`

```python
@dataclass(frozen=True)
class RawStreamEventDTO(DataTransferObject):
    event_type: str
    data: bytes
    event_id: str = ""
    timestamp: float = 0.0
```

---

## 5. Domain Exceptions

Exception taxonomy residing in `ed_transport.core.domain.exceptions`, inheriting from `DomainError`.

| Exception | Base Class | Description |
| :--- | :--- | :--- |
| `TransportError` | `DomainError` | General base class for all transport failure modes. |
| `TransportTimeoutError` | `DomainError` | HTTP socket read/connect timeout exceeded. |
| `TransportConnectionError` | `DomainError` | DNS resolution failure or network disconnect. |
| `RateLimitExceededError` | `DomainError` | Rate limiter threshold saturated without burst capacity. |
| `MaxRetriesExceededError` | `DomainError` | Maximum retry attempts exhausted without successful response. |
| `SpoolCapacityExceededError` | `DomainError` | Offline spool buffer byte quota exceeded. |
| `InvalidPayloadTypeError` | `DomainError` | Payload supplied as non-`bytes`/non-`str` (e.g. dict or domain model). |
