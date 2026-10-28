---
title: "Use-Case Specification: UC-02 Spool and Drain Offline Telemetry Requests"
use_case_id: "UC-02"
status: "approved"
version: "1.0.0"
level: "sea_level"
primary_actor: "Downstream Egress Client (ed-eddn, ed-connectors)"
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
tags: ["use-case", "requirements", "transport", "offline", "spooling", "resilience"]
---

# Use-Case Specification: UC-02 Spool and Drain Offline Telemetry Requests

## 1. System Boundary and Scope

```text
+-----------------------------------------------------------------------------------+
| System Boundary: ed-transport (Offline Spooling & Queue Resilience)                |
|                                                                                   |
|  [Actor: Downstream Egress Client]                                                |
|       |                                                                           |
|       | 1. enqueue_or_send(HttpRequestDTO)                                        |
|       v                                                                           |
|  +------------------------+   Host Disconnected   +----------------------------+  |
|  | Immediate Dispatch     | --------------------> | Bounded FIFO Spool Buffer  |  |
|  | (UC-01)                |                       | (In-Memory / SQLite Spill) |  |
|  +------------------------+                       +----------------------------+  |
|       |                                                         |                 |
|       | Host Network Restored                                   |                 |
|       +---------------------------------------------------------+                 |
|       v                                                                           |
|  [Remote Destination Endpoint] (EDDN / Inara / EDSM)                              |
+-----------------------------------------------------------------------------------+
```

### 1.1 In-Scope (Within `ed-transport` Boundary)
* Transparent interception of non-urgent outbound requests when network is detected as down or unreachable.
* Bounded FIFO request buffering with configurable memory ceilings and optional disk spooling.
* Automated queue draining when connectivity is restored, honoring destination rate limits and batching constraints.
* Eviction policy enforcement (drop oldest vs. reject newest) upon buffer saturation to guarantee host memory safety.

### 1.2 Out-of-Scope (External to `ed-transport` Boundary)
* Monitoring local Wi-Fi or operating system network interfaces directly (handled via socket reachability probes).
* Inspecting payload semantic urgency (whether an event is combat critical vs. background trade).
* Modifying telemetry event content or timestamps during buffer residency.

---

## 2. Actors and Stakeholders

* **Primary Actor:** Downstream Egress Client (`ed-eddn`, `ed-connectors`).
* **Secondary Actor (Driven):** Destination Telemetry Ingest Server.
* **Stakeholder (Operator):** Demands flight records generated during transient internet hiccups or travel do not vanish, while guaranteeing the app never consumes excessive RAM.

---

## 3. Pre-conditions and Post-conditions

### 3.1 Pre-conditions
1. Client initializes an `ed-transport` queue adapter configuring `max_queue_capacity` and `drop_policy`.
2. Outbound requests are flagged as idempotent or safe for delayed submission.

### 3.2 Post-conditions
* **Success Guarantee:** Buffered requests were safely staged in memory/disk and sequentially drained in chronological FIFO order without violating destination rate limits upon network restoration.
* **Saturation Guarantee:** When buffer capacity is exceeded, the configured eviction policy (`DropOldest` or `RejectNewest`) was strictly applied, recording an audit counter without leaking memory.

---

## 4. Main Success Scenario (Basic Flow)

1. **Submission Attempt:** Primary Actor dispatches an outbound telemetry payload via `transport_client.send_buffered(request: HttpRequestDTO)`.
2. **Network Reachability Evaluation:** System attempts standard execution ([UC-01](0001_dispatch_resilient_http_request.md)). Destination host is unreachable (DNS failure, `ENETUNREACH`, or connection timeout).
3. **Queue Enqueuing:** System transitions the request into the internal `BoundedSpoolBuffer` with timestamp and monotonic sequence ID.
4. **Offline Mode Activation:** System trips the destination circuit breaker into `HALF_OPEN` / `OFFLINE` state, suppressing immediate network attempts for subsequent requests.
5. **Periodic Liveness Probing:** Background probe periodically tests socket connectivity using an exponential health check ping.
6. **Network Restoration:** Probe succeeds; system resets circuit breaker to `CLOSED` / `ONLINE`.
7. **Drain Execution:** System sequentially drains spool buffer items, executing [UC-01](0001_dispatch_resilient_http_request.md) for each queued item in strict FIFO order while honoring token-bucket rate limits.
8. **Buffer Depleted:** System emits a queue-drained telemetry notification and returns to normal pass-through dispatch.

---

## 5. Extensions (Alternative Flows)

### 3a. Spool Buffer Saturated (Memory Limit Reached)
* `3a1.` Enqueue request occurs while buffer size equals `max_queue_capacity`.
* `3a2.` If eviction policy is `DropOldest`:
  * System evicts and drops the oldest queued record.
  * System records dropped event metric with destination identifier.
  * System enqueues the new incoming request.
* `3a3.` If eviction policy is `RejectNewest`:
  * System rejects the new incoming request and returns `QueueCapacityExceededError` to caller.

### 7a. Non-Transient Failure During Drain (Downstream Schema Rejection 400 / 422)
* `7a1.` A queued request is drained and executed, but remote destination returns a non-retryable client error (`HTTP 400 Bad Request` or `HTTP 422 Unprocessable Entity`).
* `7a2.` System recognizes the payload is permanently invalid; retrying is futile.
* `7a3.` System moves the invalid payload to a dead-letter quarantine structure, logs an error diagnostic, and immediately proceeds to drain the next queued item (preventing Head-of-Line blocking).
