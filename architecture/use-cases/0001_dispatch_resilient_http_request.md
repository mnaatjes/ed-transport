---
title: "Use-Case Specification: UC-01 Dispatch Resilient HTTP Request"
use_case_id: "UC-01"
status: "approved"
version: "1.1.0"
level: "sea_level"
primary_actor: "Downstream Integration Client (ed-capi, ed-eddn, ed-connectors, ed-state)"
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
tags: ["use-case", "requirements", "transport", "http", "retry", "rate-limiting", "bidirectional"]
---

# Use-Case Specification: UC-01 Dispatch Resilient HTTP Request

## 1. System Boundary and Scope

```text
+-----------------------------------------------------------------------------------+
| System Boundary: ed-transport (Bidirectional HTTP Engine & Network Core)          |
|                                                                                   |
|  [Actor: Downstream Client]                                                       |
|       |                                                                           |
|       | 1. send(HttpRequestDTO) [GET, POST, PUT, DELETE]                          |
|       v                                                                           |
|  +--------------------+    +---------------------+    +------------------------+  |
|  | Rate Limit Gate    | -> | Credential Injection| -> | Resilient Retry Engine |  |
|  +--------------------+    +---------------------+    +------------------------+  |
|                                                                    |              |
|                                                                    v              |
|                                                     [Target HTTP Endpoint]        |
|                                                     (EDDN / Inara / CAPI / Telemetry)
+-----------------------------------------------------------------------------------+
```

### 1.1 In-Scope (Within `ed-transport` Boundary)
* Bidirectional HTTP exchange: Dispatches both outbound egress payloads (`POST`, `PUT`) and query requests (`GET`, `DELETE`) to external and local endpoints.
* Acceptance of typed, immutable HTTP request DTOs (`url`, `method`, `headers`, `query_params`, `body_bytes`, `timeout`).
* Destination-specific rate-limiting enforcement via token-bucket and sliding-window algorithms.
* Authentication credential resolution and header injection via pluggable `CredentialProvider` ports (supporting pre-shared keys, Bearer tokens, and basic auth).
* Automated retry loop with exponential backoff and randomized decorrelated jitter for transient network failures (`5xx`, socket timeout, connection reset).
* Dispassionate, sanitized response wrapping into typed `HttpResponseDTO` with header masking for sensitive security credentials.

### 1.2 Out-of-Scope (External to `ed-transport` Boundary)
* **Domain Data Modeling:** Parsing Elite Dangerous telemetry events, journal records, or cockpit state (governed by `ed-models` and `ed-telemetry`).
* **Schema Validation:** Verifying that payload bodies comply with EDDN JSON schemas or Inara API contracts (governed by `ed-eddn` and `ed-connectors`).
* **OAuth2 Grant Negotiation:** Managing Frontier authorization code redirection, browser handshakes, or PKCE verifier generation (governed by `ed-capi`).
* **Application Logging Configuration:** Configuring root loggers, formatters, or file rotators on disk (owned by the host application).
* **Persistent Database Storage:** Schema creation, migrations, or relational tables (owned by consumer packages).

---

## 2. Actors and Stakeholders

* **Primary Actor:** Downstream Integration Client (`ed-capi`, `ed-eddn`, `ed-connectors`, `ed-state`).
* **Secondary Actor (Driven):** Remote Destination Server (e.g. `eddn.edcd.io`, `inara.cz/api/v2`, Frontier CAPI, or local `ed-telemetry`).
* **Stakeholder (Operator):** Demands zero unhandled crashes, zero telemetry loss during transient glitches, protection against IP bans from third-party APIs, and zero credential leakage.

---

## 3. Pre-conditions and Post-conditions

### 3.1 Pre-conditions
1. Client application has instantiated `ed-transport` via `create_transport_client()` or container composition root.
2. Target URL scheme is valid (`http://` or `https://`).
3. If authentication is required, a corresponding `CredentialProvider` port is attached to the client instance.

### 3.2 Post-conditions
* **Success Guarantee:** The request reached the destination server, completed within timeout bounds, and a normalized `HttpResponseDTO` containing status code, headers, and body bytes was returned to the caller.
* **Failure Guarantee (Minimal Guarantee):** If retries were exhausted or a terminal error occurred (`4xx` client error, invalid TLS certificate), execution halted safely, resources were freed, no unredacted credentials were leaked to loggers, and a typed `TransportError` was returned.

---

## 4. Main Success Scenario (Basic Flow)

1. **Request Submission:** Primary Actor calls `transport_client.send(request: HttpRequestDTO)`.
2. **Rate Limit Audit:** System queries the destination's active `RateLimiterPort`. Token is available; request proceeds immediately.
3. **Credential Injection:** System queries the configured `CredentialProviderPort`. Credentials (Bearer token, API key header, or Basic Auth) are applied to the outbound request headers.
4. **Wire Transmission:** System dispatches the request over the network via `HttpEnginePort` with configured connect and read timeouts.
5. **Successful Response:** Destination server returns an HTTP status in the `2xx` or `3xx` range.
6. **Telemetry Metric Recording:** System records request latency and increments successful transmission counters.
7. **Response Delivery:** System returns an immutable `HttpResponseDTO` to the Primary Actor.

---

## 5. Extensions (Alternative Flows)

### 2a. Rate Limit Exceeded (Throttling)
* `2a1.` System detects token-bucket exhaustion or destination cooldown active.
* `2a2.` If client configured blocking execution (`blocking=True`):
  * System pauses caller execution thread for calculated backoff period ($\le \text{max\_wait\_seconds}$).
  * Upon timer expiration, system consumes a replenished token and resumes at Step 3.
* `2a3.` If client configured non-blocking execution (`blocking=False`) or wait ceiling exceeded:
  * System aborts transmission and raises `RateLimitExceededError` containing `retry_after_seconds`.

### 4a. Network Timeout / Connection Reset / 5xx Server Error (Transient Failure)
* `4a1.` Network dispatch fails due to socket timeout, DNS failure, connection reset, or returns an HTTP `500`, `502`, `503`, or `504`.
* `4a2.` System evaluates active `RetryPolicy`:
  * If current attempt count $<$ `max_retries`:
    * System computes sleep delay using exponential backoff with full jitter:
      $$\text{delay} = \text{uniform}(0, \min(\text{max\_backoff}, \text{base\_delay} \times 2^{\text{attempt}}))$$
    * System pauses execution for computed duration and increments attempt counter.
    * System resumes at Step 2 (re-checking rate limits and re-dispatching).
  * If attempt count $\ge$ `max_retries`:
    * System logs warning with sanitized endpoint details.
    * System raises `MaxRetriesExceededError` bundling root cause exception and attempt history.

### 5a. HTTP 401 Unauthorized / Token Expiry
* `5a1.` Destination server returns `HTTP 401 Unauthorized`.
* `5a2.` If `CredentialProviderPort` supports dynamic token invalidation:
  * System notifies provider via `credential_provider.invalidate()`.
  * System requests refreshed token and re-executes request once.
* `5a3.` If re-execution fails or provider does not support refresh:
  * System wraps response and returns `HttpResponseDTO(status_code=401)` to caller without retrying (terminal failure).

### 5b. HTTP 429 Too Many Requests (Downstream Backoff Signal)
* `5b1.` Destination server returns `HTTP 429 Too Many Requests` with optional `Retry-After` header.
* `5b2.` System parses `Retry-After` header (seconds or RFC 1123 HTTP date).
* `5b3.` System updates destination rate-limiter state with mandated cooldown.
* `5b4.` If attempt budget allows, system sleeps for mandated duration and retries at Step 2; otherwise raises `RateLimitExceededError`.
