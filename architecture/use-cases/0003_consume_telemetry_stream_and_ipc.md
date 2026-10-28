---
title: "Use-Case Specification: UC-03 Consume Telemetry Stream and Local Daemon IPC"
use_case_id: "UC-03"
status: "approved"
version: "1.0.0"
level: "sea_level"
primary_actor: "Downstream Consumer (ed-state, ed-connectors, ed-cli)"
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
tags: ["use-case", "requirements", "transport", "sse", "stream", "ipc", "telemetry"]
---

# Use-Case Specification: UC-03 Consume Telemetry Stream and Local Daemon IPC

## 1. System Boundary and Scope

```text
+-----------------------------------------------------------------------------------+
| System Boundary: ed-transport (Local Daemon IPC & Event Stream Transport)         |
|                                                                                   |
|  [Actor: Downstream Consumer]                                                     |
|       |                                                                           |
|       | 1. open_stream(topic=...)                                                 |
|       v                                                                           |
|  +--------------------+    +---------------------+    +------------------------+  |
|  | Auth Gate (API Key)| -> | Chunked SSE Parser  | -> | Connection Watchdog    |  |
|  +--------------------+    +---------------------+    +------------------------+  |
|                                                                    |              |
|                                              HTTP SSE Connection  |              |
|                                                                    v              |
|                                                [ed-telemetry Daemon]              |
|                                                http://127.0.0.1:8080/api/v1/stream|
+-----------------------------------------------------------------------------------+
```

### 1.1 In-Scope (Within `ed-transport` Boundary)
* Establishing persistent HTTP Server-Sent Events (SSE) connections to local or remote `ed-telemetry` instances.
* Pre-shared API key authorization header injection (`Authorization: Bearer <ED_API_KEY>`).
* Chunked SSE wire protocol parsing (demuxing `event`, `data`, and heartbeat comment lines `:\n\n`).
* Heartbeat watchdog monitoring and automated reconnection with exponential backoff if the local daemon process is restarted or temporarily offline.
* Delivering raw, validated telemetry string/bytes payloads to the consumer's message handler.

### 1.2 Out-of-Scope (External to `ed-transport` Boundary)
* Deserializing event JSON into high-level game entities (`FSDJump`, `Cargo`, etc. - handled by `ed-models`).
* Maintaining aggregated player state, loadouts, or flight history (handled by `ed-state`).
* Managing local daemon process lifecycle (`systemd`, background subprocess spawn - handled by OS/CLI).

---

## 2. Actors and Stakeholders

* **Primary Actor:** Downstream Consumer (`ed-state`, `ed-connectors`, `ed-cli`).
* **Secondary Actor (Driven):** Running `ed-telemetry` Daemon.
* **Stakeholder (Operator):** Demands seamless recovery when the background daemon reloads, without crashing client applications or requiring manual reconnect triggers.

---

## 3. Pre-conditions and Post-conditions

### 3.1 Pre-conditions
1. `ed-transport` client configured with base URL (e.g. `http://127.0.0.1:8080`) and optional API key.
2. Consumer provides an event callback or async iterator to receive streaming items.

### 3.2 Post-conditions
* **Success Guarantee:** Continuous stream of raw telemetry events delivered to consumer with minimal latency.
* **Resilience Guarantee:** When connection drops, system continuously attempts reconnection with exponential backoff up to configured limit without leaking memory or file descriptors.

---

## 4. Main Success Scenario (Basic Flow)

1. **Stream Connection:** Consumer calls `transport_client.open_stream(endpoint="/api/v1/stream", topic=...)`.
2. **Authentication Injection:** System resolves the active API key and attaches `Authorization: Bearer <key>` header.
3. **HTTP Handshake:** System opens streaming HTTP GET request with `Accept: text/event-stream`.
4. **Daemon Acceptance:** Daemon returns `HTTP 200 OK` with `Content-Type: text/event-stream`.
5. **Frame Demuxing:** System reads chunked stream chunks, parses `data: {...}` lines, and strips transport framing.
6. **Payload Dispatch:** System yields each event payload to the consumer iterator/callback.
7. **Heartbeat Processing:** System detects SSE heartbeat keep-alive frames and resets watchdog timer.
8. **Graceful Close:** Consumer signals shutdown; system cleanly closes socket connection.

---

## 5. Extensions (Alternative Flows)

### 3a. Daemon Offline / Connection Refused (`ECONNREFUSED`)
* `3a1.` Connection attempt fails because `ed-telemetry` daemon is not yet running.
* `3a2.` System logs diagnostic message: "Local telemetry daemon unreachable at {host}:{port}, retrying in {delay}s...".
* `3a3.` System pauses for exponential backoff duration ($\le \text{max\_reconnect\_delay}$).
* `3a4.` System resumes at Step 2.

### 4a. Daemon Authentication Rejected (`HTTP 401 Unauthorized`)
* `4a1.` Daemon returns `HTTP 401 Unauthorized` (invalid or missing `ED_API_KEY`).
* `4a2.` System halts reconnection loop immediately (terminal security failure).
* `4a3.` System raises `AuthenticationFailedError` with actionable instruction to configure credentials via `ed-telemetry auth show`.

### 6a. Mid-Stream Socket Dropout / Daemon Restart
* `6a1.` Socket drops unexpectedly or read times out exceeding watchdog ceiling.
* `6a2.` System emits a `StreamDisconnected` diagnostic notification.
* `6a3.` System initiates reconnection cycle at Step 2 with full jitter backoff.
