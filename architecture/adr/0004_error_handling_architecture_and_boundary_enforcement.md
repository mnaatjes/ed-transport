---
title: "ADR 0004: Error Handling Architecture and Boundary Enforcement"
status: "accepted"
date: "2026-10-28"
deciders: ["Core Architecture Team"]
consulted: ["ADR 0001", "ADR 0002", "ADR 0003", "UC-01", "UC-02", "UC-04", "RISK-01", "RISK-02", "RISK-05", "RISK-10"]
informed: ["All Engineers", "Downstream Consumer Authors (ed-capi, ed-eddn, ed-connectors, ed-telemetry)"]
tags: ["adr", "architecture", "error-handling", "exceptions", "resilience", "hexagonal", "boundary-enforcement"]
---

# ADR 0004: Error Handling Architecture and Boundary Enforcement

## Context and Problem Statement

`ed-transport` serves as the foundational HTTP delivery and IPC streaming engine across the *Elite Dangerous* software fleet (`ed-capi`, `ed-eddn`, `ed-connectors`, `ed-state`, `ed-telemetry`). Because `ed-transport` is a shared dependency and not a standalone process, its error handling strategy directly determines whether downstream consumers remain resilient or suffer catastrophic failures.

Improper error handling in transport libraries introduces severe architectural hazards:
1. **Third-Party Type Leaks:** If driven engine adapters (e.g. `httpx`, `aiohttp`, `urllib3`, `sqlite3`) allow raw exceptions to escape into consumer code, consuming packages become coupled to specific HTTP engine implementations, violating Hexagonal Architecture.
2. **Ambiguous Failure Semantics:** Downstream consumers cannot distinguish between transient recoverable network hiccups (TCP resets, rate limits, 503 Service Unavailable) and unrecoverable client errors (invalid URLs, malformed payloads).
3. **Thundering Herd / Retry Storms:** Naive retry loops without randomized decorrelated jitter saturate external community APIs (Frontier CAPI, EDDN gateways, Inara API) during outages.
4. **Overstepping Boundary Authority:** Libraries that attempt to format user-facing dialogs, trigger interactive credential prompts, or invoke `sys.exit()` hijack host application control flows.

How should `ed-transport` structure its exception taxonomy, adapter translation boundaries, retry policies, and automated scope enforcement?

---

## Decision Drivers

* **Pure Hexagonal Isolation:** Outer application consumers must never catch or import third-party transport engine exceptions (`httpx.HTTPError`, `aiohttp.ClientError`, `socket.error`, `sqlite3.Error`).
* **Explicit In-Scope vs Out-of-Scope Demarcation:** The transport must manage transport-level failure resilience, while host applications maintain sovereign control over recovery workflows, process termination, and user alerting.
* **Preservation of Diagnostic Context:** All translated exceptions must maintain complete causal traceability (`raise DomainException(...) from raw_err`) and attach contextual diagnostic metadata (`endpoint`, `timeout_seconds`, `attempt_count`, `correlation_id`).
* **Ergonomic Facade Integrity:** The driving adapter facades (`TransportClient` and `AsyncTransportClient`) must expose clear configuration contracts (`RetryConfig`, `RateLimitConfig`, `SpoolConfig`) without polluting signatures with host-level recovery hooks.

---

## Considered Options

* **Option 1: Transparent Third-Party Exception Passthrough.** Allow the underlying HTTP engine's exceptions (`httpx.RequestError`, `httpx.HTTPStatusError`) to bubble directly through ports and facades to consumers. *(Rejected: Severely violates Hexagonal Architecture; couples all fleet packages to the internal engine adapter; breaks if the HTTP engine is swapped)*.
* **Option 2: Generic Exception Flattening.** Catch all internal exceptions and raise a single generic `TransportError("request failed")`. *(Rejected: Destroys diagnostic specificity; prevents consumers from implementing targeted recovery strategies like backing off on rate limits vs buffering offline)*.
* **Option 3: Pure Domain Exception Taxonomy with Driven Adapter Translation and Policy-Driven Resilience.** Establish a strongly typed exception hierarchy rooted at `DomainError`, enforce mandatory error translation inside driven adapters, provide policy-driven retry/spool fallback, and mechanically forbid host-level error mutations via AST checks.

---

## Decision Outcome

Chosen Option: **Option 3: Pure Domain Exception Taxonomy with Driven Adapter Translation and Policy-Driven Resilience**.

### 1. In-Scope Error Handling Responsibilities for `ed-transport`

#### A. Pure Domain Exception Taxonomy
All transport subsystem errors inherit strictly from `DomainError` in `src/ed_transport/core/domain/exceptions.py`:

```text
DomainError (root)
├── TransportError
│   ├── TransportTimeoutError (endpoint, timeout_seconds, attempt_count)
│   ├── TransportConnectionError (endpoint, details)
│   ├── RateLimitExceededError (destination_key, retry_after_seconds)
│   └── MaxRetriesExceededError (endpoint, total_attempts, last_error)
├── SpoolCapacityExceededError (current_depth, capacity_ceiling)
├── InvalidPayloadTypeError (invalid_type)
├── DomainValidationError
└── HealthCheckFailedError
```

#### B. Driven Adapter Exception Translation (Boundary Sanitization)
Driven adapters implementing secondary SPIs (e.g. `HttpEnginePort`, `SpoolStoragePort`) must intercept all engine-specific and OS-level exceptions and translate them into domain exceptions before crossing the hexagon boundary:

```python
# Inside driven adapter:
try:
    response = self._client.send(request)
except httpx.ConnectTimeout as err:
    raise TransportTimeoutError(
        endpoint=request.url,
        timeout_seconds=request.timeout,
        attempt_count=attempt
    ) from err
except httpx.NetworkError as err:
    raise TransportConnectionError(
        endpoint=request.url,
        details=str(err)
    ) from err
except sqlite3.OperationalError as err:
    raise SpoolCapacityExceededError(
        current_depth=self.depth,
        capacity_ceiling=self.max_capacity
    ) from err
```

#### C. Retry and Decorrelated Jitter Policies
The core use cases automatically execute retry loops for transient failure modes (HTTP status codes `429`, `502`, `503`, `504`, and socket connection resets) governed by `RetryConfig`:

```python
@dataclass(frozen=True)
class RetryConfig:
    max_retries: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 60.0
    jitter_factor: float = 0.5
```

When retries are exhausted, the interactor raises `MaxRetriesExceededError` containing the total attempts executed and chaining the final underlying domain exception.

#### D. Fail-Safe Offline Spool Fallback
When dispatching via `send_buffered()`, recoverable transport failures (`TransportConnectionError`, `TransportTimeoutError`) are trapped internally by the interactor. The request payload is diverted into the offline spool buffer:
* Returns `True` if dispatched immediately or successfully buffered.
* If the spool buffer is saturated and configured with `overflow_strategy="reject"`, raises `SpoolCapacityExceededError`.

#### E. Diagnostic Error Context Preservation
Domain exceptions must preserve rich diagnostic context (`endpoint`, `timeout_seconds`, `attempt_count`, `correlation_id`) and enforce Python exception chaining (`from err`) to preserve the original traceback for post-mortem analysis.

---

### 2. Explicit Out-of-Scope Boundaries for `ed-transport`

The following error handling concerns belong exclusively to host applications and are strictly **out-of-scope** for `ed-transport`:

1. **Host Application Recovery Workflows:**
   * Deciding whether the host application should retry at the task/workflow level, abort, discard an event, or pause execution.
   * Modifying application-specific business state in response to transport errors.
2. **User-Facing Error Presentation & Alerting:**
   * Formatting localized error strings for GUI dialogs, TUI notifications, or terminal display.
   * Emitting alerts to external monitoring services (Sentry, Bugsnag, PagerDuty).
3. **Interactive Recovery Gates:**
   * Prompting users to re-authenticate, refresh expired tokens, or troubleshoot network adapters.
4. **Process Termination & Exit Code Management:**
   * Invoking `sys.exit()` or `os._exit()`, or managing process return codes.
5. **Payload-Specific Content Error Handling:**
   * Parsing or validating game journal schemas or remote business error bodies (e.g. Frontier CAPI JSON error structures vs EDDN JSON schema validation failures). The transport engine only evaluates HTTP status codes and delivers raw payload bytes.

---

### 3. Driving Facade Impact and Parameter Surface

The driving adapter facades (`TransportClient` and `AsyncTransportClient`) maintain clean, parameter-driven policy boundaries:

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

* **No Error Callback Hooks:** The facade does not accept error callback lambdas or recovery handlers; errors are communicated cleanly via standard Python exception propagation.
* **No Process Control Parameters:** The facade contains zero parameters related to process termination or exit behaviors.
* **Domain Exception Transparency:** Consumers wrap facade calls with standard Python `try / except TransportError:` blocks.

---

## Mechanical Boundary Enforcement Mechanisms

To verify that these error handling invariants are never breached, `tests/architecture/test_boundaries.py` enforces the following static AST quality gates:

1. **Forbid Process Termination (`sys.exit` / `os._exit`):**
   * Scans all AST `Call` nodes across `src/ed_transport/`; asserts zero invocations of `sys.exit()`, `os._exit()`, or `raise SystemExit`.
2. **Forbid Third-Party Exception Leaks in Port Signatures:**
   * Inspects all type annotations and docstrings in `src/ed_transport/core/ports/` to verify zero references to third-party exception classes (`httpx.*`, `aiohttp.*`, `requests.*`, `urllib3.*`, `sqlite3.*`).
3. **Enforce Domain Exception Inheritance:**
   * Verifies that every exception class defined in `src/ed_transport/core/domain/exceptions.py` inherits directly or transitively from `DomainError`.
4. **Enforce Exception Chaining in Driven Adapters:**
   * Asserts that `raise` statements within driven adapter `except` blocks explicitly specify `from <exception>` to preserve causal traceback integrity.

---

## Consequences

### Positive
* Downstream applications remain 100% decoupled from underlying network libraries and HTTP engines.
* Standardized, strongly typed exception hierarchy simplifies error handling across all consumer packages.
* Automated jittered retries eliminate thundering herd hazards against community services.
* Automated AST linters prevent process hijacking or third-party type contamination.

### Negative / Trade-offs
* Driven adapters must maintain explicit try/except translation blocks for all low-level engine exceptions.
* Consuming applications must catch `ed_transport` domain exceptions rather than standard library socket errors.
