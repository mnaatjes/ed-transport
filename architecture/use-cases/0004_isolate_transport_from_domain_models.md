---
title: "Use-Case Specification: UC-04 Isolate Transport from Domain Models"
use_case_id: "UC-04"
status: "approved"
version: "1.0.0"
level: "sea_level"
primary_actor: "Downstream Integration Client (ed-capi, ed-eddn, ed-connectors, ed-state)"
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
tags: ["use-case", "requirements", "transport", "domain-boundary", "ed-models", "hexagonal"]
---

# Use-Case Specification: UC-04 Isolate Transport from Domain Models

## 1. System Boundary and Scope

```text
+-----------------------------------------------------------------------------------+
| System Boundary: ed-transport vs Planned ed-models Boundary Partition            |
|                                                                                   |
|  [Actor: Downstream Client (ed-eddn, ed-capi, ed-connectors)]                    |
|       |                                                                           |
|       | 1. Serializes domain models (from ed-models) into raw wire format         |
|       |    (e.g., JSON bytes, raw string, octet-stream)                           |
|       |                                                                           |
|       | 2. Passes opaque payload to ed-transport:                                 |
|       |    HttpRequest(url, method, headers, body=bytes)                         |
|       v                                                                           |
|  +-----------------------------------------------------------------------------+  |
|  | ed-transport Core Engine                                                     |  |
|  | * Dispatches opaque byte/text buffer via HTTP socket engine                 |  |
|  | * ZERO imports from ed-models or Elite Dangerous game structures           |  |
|  | * ZERO semantic validation of payload content                              |  |
|  | * Returns raw HttpResponse(status_code, headers, body=bytes)                |  |
|  +-----------------------------------------------------------------------------+  |
|       |                                                                           |
|       | 3. Returns raw response bytes to Actor                                    |
|       v                                                                           |
|  [Actor parses response bytes using ed-models schemas or domain parsers]          |
+-----------------------------------------------------------------------------------+
```

### 1.1 In-Scope (Within `ed-transport` Boundary)
* Acceptance of raw, serialized payloads (`bytes`, `str`, or binary stream iterators) in all driving transport interfaces (`HttpRequest`, `SpoolItem`).
* Returning raw, unparsed response bodies (`bytes`, `str`, or chunked byte iterators) in `HttpResponse`.
* Transport-level headers injection and serialization (e.g., `Content-Type`, `Content-Length`, `Authorization`, `User-Agent`).
* Offline spooling and circular buffering of raw byte payloads without schema introspection.
* Deterministic lint and architecture gate enforcement (`lint-imports`, `pytest-archon`) ensuring `ed-transport` has zero runtime or static import dependencies on `ed-models`.

### 1.2 Out-of-Scope (Strictly Reserved for `ed-models` & Downstream Consumers)
* **Domain Model Definitions:** Declaring Elite Dangerous journal event structures (`FSDJump`, `Docked`, `Location`, `Market`, `Shipyard`), module slot layouts, commodity enums, or commander attributes (reserved for `ed-models`).
* **Schema Validation:** Verifying EDDN JSON-Schema conformity or Inara/EDSM schema compatibility (reserved for `ed-eddn`, `ed-connectors`).
* **Serialization / Deserialization Logic:** Converting Pydantic, Msgspec, or dataclass models to/from JSON or binary payloads (handled by consumers using `ed-models`).
* **Semantic Error Interpretation:** Evaluating business errors embedded inside HTTP 200 responses (e.g. Inara API error status flags, Frontier account validation codes) beyond standard HTTP protocol status codes.

---

## 2. Actors and Stakeholders

* **Primary Actor:** Downstream Integration Client (`ed-capi`, `ed-eddn`, `ed-connectors`, `ed-state`).
* **Governing Dependency:** Planned `ed-models` package (shared foundational data schemas and enums).
* **Stakeholder (Architect / Core Team):** Requires total isolation between network mechanics and domain contracts so that updates to game events, schemas, or models never require a release or rebuild of `ed-transport`.

---

## 3. Pre-conditions and Post-conditions

### Pre-conditions
1. The downstream client has resolved any domain representations from `ed-models`.
2. The downstream client has serialized the domain model into a byte payload or string appropriate for the target wire protocol.
3. The downstream client configures the `HttpRequest` DTO with appropriate destination URL, headers, and the raw payload.

### Post-conditions
1. `ed-transport` dispatches the payload across the network without mutating or inspecting the content bytes.
2. The target server response is delivered back to the downstream client as unparsed `bytes` or `str`.
3. No domain entity or schema dependency from `ed-models` is introduced into `ed-transport`.

---

## 4. Main Success Scenario (Basic Flow)

1. **Serialization Outside Transport:** The downstream client takes a strongly typed event instance from `ed-models` (e.g., `FSDJumpEvent`) and serializes it to JSON `bytes`.
2. **Dispatch Invocation:** The client creates an `HttpRequest` specifying `method="POST"`, target endpoint URL, headers (`{"Content-Type": "application/json"}`), and `body=serialized_bytes`.
3. **Transport Processing:** `ed-transport` applies destination rate-limiting, injects configured authentication credentials, and sends the raw bytes over the socket via `HttpEnginePort`.
4. **Response Delivery:** `ed-transport` receives the socket response and packages status code, response headers, and unparsed body bytes into an `HttpResponse` DTO.
5. **Consumption & Parsing:** The downstream client receives the `HttpResponse` and uses its own domain parsers / `ed-models` to deserialize and validate the response body.

---

## 5. Alternate Flows

### 5a. Offline Spooling of Payloads
1. At step 3 of Main Success Scenario, if the network is unavailable and spooling is active, `ed-transport` enqueues the request.
2. The spooling engine stores the raw URL, headers, and body bytes to in-memory circular buffers or disk storage without inspecting domain types.
3. When connectivity restores, the drained requests are dispatched using the preserved raw bytes.

### 5b. Invalid Wire Payload
1. At step 3 of Main Success Scenario, if the target server rejects the payload with HTTP 400 Bad Request (e.g., due to downstream schema mismatch), `ed-transport` treats this as a standard terminal HTTP error.
2. `ed-transport` records telemetry metrics and returns the 400 `HttpResponse` directly to the client without attempting to remediate or understand the schema failure.

---

## 6. Boundary Invariants and Architectural Requirements

* **REQ-BOUND-01 (Zero Model Imports):** Under no circumstance may any module under `src/ed_transport/` import from `ed_models` or reference game event structures.
* **REQ-BOUND-02 (Payload Agnosticism):** The transport core must accept `bytes`, `str`, or binary generators, treating payloads as opaque sequences.
* **REQ-BOUND-03 (Independent Release Lifecycle):** `ed-transport` must be capable of versioning, releasing, and deploying independently of changes to Elite Dangerous game updates or `ed-models` schema expansions.
