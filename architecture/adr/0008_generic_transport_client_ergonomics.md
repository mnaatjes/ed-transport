---
title: "ADR 0008: Generic Transport Client Ergonomics and Protocol Usability"
status: "accepted"
date: "2026-10-29"
deciders: ["Core Architecture Team"]
consulted: ["ADR 0001", "ADR 0002", "ADR 0005", "UC-01", "UC-04"]
informed: ["All Engineers", "Consumer Package Authors (ed-capi, ed-eddn, ed-connectors)"]
tags: ["adr", "ergonomics", "client", "json", "http", "api-surface", "hexagonal"]
---

# ADR 0008: Generic Transport Client Ergonomics and Protocol Usability

## Context and Problem Statement

`ed-transport` serves as the foundational HTTP transport and telemetry delivery engine across the *Elite Dangerous* software fleet (`ed-capi`, `ed-eddn`, `ed-connectors`). Per [ADR 0001](file:///home/michael/src/github.com/mnaatjes/ed-transport/architecture/adr/0001_scope_and_boundary_enforcement_mechanisms.md) and [UC-04](file:///home/michael/src/github.com/mnaatjes/ed-transport/architecture/use-cases/0004_isolate_transport_from_domain_models.md), the transport core must remain 100% agnostic to Elite Dangerous game entities, domain models, and third-party proprietary schemas (e.g. Inara envelopes, EDDN schemas).

However, in its initial as-built implementation, consumer libraries must manually perform low-level serialization and protocol boilerplate for every outbound dispatch:
1. **Manual JSON Encoding:** Callers must import Python's standard `json` module, manually serialize dictionaries with `json.dumps(data).encode("utf-8")`, and explicitly inject `"Content-Type": "application/json"` into header maps.
2. **Manual Response Deserialization:** Callers receiving `HttpResponseDTO` must manually invoke `json.loads(response.body.decode("utf-8"))` for every REST payload.
3. **Repeated Header Injection:** Client identity headers (such as `User-Agent: EDCD-Fleet/1.0` or static Authorization tokens) must be passed repeatedly on every individual call to `client.get()`, `client.post()`, or `send_buffered()`.
4. **Repetitive Error Checking:** Code inspecting responses must repeatedly write conditional checks (`if not response.is_success:` or `if response.status_code >= 400:`) to raise domain transport exceptions.

How can `ed-transport` provide modern, zero-friction HTTP client ergonomics without violating Hexagonal boundary rules or introducing domain dependencies?

---

## Decision Drivers

* **Zero Domain Knowledge (Total Model Agnosticism):** The library must continue to operate strictly on standard Python primitives (`dict`, `list`, `str`, `bytes`) without importing domain libraries (`ed_models`, `pydantic`, `jsonschema`).
* **Developer Experience (DX) Parity:** Provide familiar ergonomics standard in modern Python HTTP libraries (e.g., `requests`, `httpx`).
* **Hexagonal Boundary Purity:** Convenience abstractions must reside strictly on the Driving Adapter facade (`adapters/driving/client.py`) and boundary DTOs (`core/ports/dto/transport_dto.py`), leaving core use-case interactors clean and focused on transport orchestration.
* **Offline Spooling Compatibility:** Any JSON payloads or default headers processed via ergonomic facades must serialize cleanly into `HttpRequestDTO` so offline spool buffers retain full fidelity without data loss.

---

## Considered Options

* **Option 1: Status Quo (Strict Primitive Bytes).** Require consumers (`ed-capi`, `ed-eddn`, `ed-connectors`) to handle all JSON serialization, header repetition, and status code verification manually in their own codebases. *(Rejected: Unnecessary cognitive load and repeated boilerplate across 3+ downstream repositories).*
* **Option 2: Embed Domain Envelopes into `ed-transport`.** Provide specific builders for Inara, EDSM, and EDDN payloads inside `ed-transport`. *(Rejected: Severe architectural boundary violation; couples transport releases to third-party API schema updates).*
* **Option 3: Generic Protocol Ergonomics on Facades and DTOs.** Introduce five generic, protocol-level conveniences into `TransportClient`, `AsyncTransportClient`, and `HttpResponseDTO`:
  1. Direct Python dictionary dispatch via `json=` parameter.
  2. One-step JSON response parsing via `response.json()`.
  3. Reusable client-level `default_headers`.
  4. Safe query string parameter assembly via `params=`.
  5. Immediate failure assertion via `response.raise_for_status()`.

---

## Decision Outcome

Chosen Option: **Option 3: Generic Protocol Ergonomics on Facades and DTOs**.

### Detailed Specification of the 5 Generic Ergonomic Features

#### 1. Direct Python Dictionary Support (`json=`)
All request dispatch methods (`post()`, `post_async()`, `put()`, `put_async()`, `send_buffered()`, `send_buffered_async()`) will accept an optional `json: Any = None` keyword argument:
* When `json` is provided and `body` is omitted:
  * Automatically serializes the object using `json.dumps(json_obj).encode("utf-8")`.
  * Automatically sets header `"Content-Type": "application/json"` if not already explicitly defined by the caller.
* If both `body` and `json` are passed simultaneously, a `DomainValidationError` is raised to prevent ambiguous payload definitions.

#### 2. One-Step Response Parsing (`response.json()`)
`HttpResponseDTO` will provide a convenience method:
```python
def json(self) -> Any:
    """Parses response body bytes as JSON object."""
```
* Decodes `self.body` as UTF-8 string and parses via `json.loads()`.
* Raises `DomainValidationError` with clear context if the response payload is empty or malformed JSON.

#### 3. Reusable Client-Level Default Headers (`default_headers`)
Both `TransportClient` and `AsyncTransportClient` (and their respective factories `create_transport_client()` / `create_async_transport_client()`) will accept:
```python
default_headers: Mapping[str, str] | None = None
```
* Stored on the client facade and automatically merged with per-request headers.
* Per-request headers take precedence over default headers in the event of key collisions (case-insensitively).

#### 4. Safe URL Query Parameter Assembly (`params=`)
Standardize `params: Mapping[str, Any] | None = None` across all dispatch verbs (`get`, `post`, `put`, `delete`):
* Transparently encodes key-value pairs into standard URL query strings using `urllib.parse.urlencode`.
* Safely appends to URLs that already contain existing query parameters (`?` vs `&`).

#### 5. Automatic Error Raising (`response.raise_for_status()`)
`HttpResponseDTO` will provide:
```python
def raise_for_status(self) -> None:
    """Raises TransportError if response represents an HTTP 4xx or 5xx error."""
```
* If `400 <= self.status_code < 500`: raises `TransportError` (or `TransportTimeoutError` if status is 408).
* If `500 <= self.status_code < 600`: raises `TransportError`.
* If `self.status_code < 400`: returns cleanly without action.

---

## Positive Consequences

* **Ergonomic DX:** Consumers write clean, idiomatic Python (`client.post(url, json=data)` and `res.json()`) identical to standard HTTP tooling.
* **Maintained Boundary Invariants:** `ed-transport` retains 100% model and domain agnosticism; zero Elite Dangerous imports or schema couplings.
* **Reduced Downstream Boilerplate:** Eliminates redundant JSON serialization, error-checking, and header-merging loops across `ed-capi`, `ed-eddn`, and `ed-connectors`.
