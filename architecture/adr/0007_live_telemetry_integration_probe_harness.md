---
title: "ADR 0007: Live Telemetry Integration Probe Harness and Host Verification"
status: "accepted"
date: "2026-10-28"
deciders: ["Core Architecture Team"]
consulted: ["ADR 0001", "ADR 0002", "ADR 0005", "ADR 0006", "UC-01", "UC-03"]
informed: ["All Engineers", "Fleet Integrators"]
tags: ["adr", "probe", "integration-testing", "live-telemetry", "sse", "host-testing"]
---

# ADR 0007: Live Telemetry Integration Probe Harness and Host Verification

## Context and Problem Statement

`ed-transport` is a foundational library providing resilient HTTP dispatch and asynchronous Server-Sent Events (SSE) stream consumption for the *Elite Dangerous* software fleet. While automated unit tests (`tests/unit/`) verify boundary contracts and protocol decoding using mock transports (`httpx.MockTransport`), automated CI pipelines strictly prohibit outbound network calls to external host IP addresses.

Operators and engineers require a concrete, repeatable mechanism to test `ed-transport` against a live, running `ed-telemetry` ingestion daemon running on a physical host (e.g., `michael-desktop` at `192.168.1.214:8080`). This real-world test must validate:
1. Physical TCP socket establishment across local area network (LAN) boundaries.
2. Synchronous REST health probe queries (`GET /api/v1/health` or `/health`).
3. Asynchronous SSE stream subscription (`GET /api/v1/stream`) with live event decoding.
4. Resilience and backoff behavior when the target daemon is offline or restarting.

How should `ed-transport` provide a live network probe tool without violating library boundary invariants or breaking isolated CI test runs?

---

## Decision Drivers

* **Zero CI Pollution:** The probe must be an explicit, optional maintenance script (`scripts/`), strictly decoupled from automated `pytest` and pre-commit test runs.
* **Dual-Mode Verification:** Must validate both synchronous request dispatch (`TransportClient`) and asynchronous stream consumption (`AsyncTransportClient`).
* **Informative Telemetry & Observability:** Clearly display connection attempts, round-trip latency, received SSE frames, event cursors (`Last-Event-ID`), and reconnect backoff intervals in the terminal.
* **Configurable Host Perimeters:** Allow dynamic override of host, port, timeout, and topic parameters via CLI flags while providing sensible defaults (`192.168.1.214:8080`).
* **Clean Teardown:** Intercept `SIGINT` (Ctrl+C) to gracefully cancel active async streams and close connection pools without unhandled tracebacks.

---

## Considered Options

* **Option 1: Include live host integration test in `tests/integration/`.** *(Rejected: External hosts are not guaranteed to be running during CI/CD execution, causing spurious build failures).*
* **Option 2: Standalone shell script invoking `curl`.** *(Rejected: Tests `curl` rather than `ed-transport`'s internal engine, rate-limiters, and DTO decoding).*
* **Option 3: Dedicated Operational Diagnostic Probe Script in `scripts/probe_live_telemetry.py`.** Implement a standalone Python script utilizing `ed-transport`'s public factory facades (`create_transport_client` and `create_async_transport_client`) to exercise both REST queries and live SSE stream ingestion against configurable host perimeters.

---

## Decision Outcome

Chosen Option: **Option 3: Dedicated Operational Diagnostic Probe Script in `scripts/probe_live_telemetry.py`**.

### Architectural Position
The probe acts as an out-of-band diagnostic driving client located in `scripts/probe_live_telemetry.py`. It consumes the public API surface defined in `src/ed_transport/__init__.py`:
* `create_transport_client`: Executes synchronous health probes.
* `create_async_transport_client`: Establishes persistent SSE subscriptions and renders live event frames.
* `RawStreamEventDTO`: Receives decoded stream frames.
