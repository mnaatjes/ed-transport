---
title: "Use-Case Discipline Governance and Index"
tags: ["architecture", "use-cases", "requirements", "governance"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# Use-Case Discipline Governance and Index

Governed by the Rational Unified Process (RUP) Use-Case Specification standard and Alistair Cockburn's Goal-Level Hierarchy.

---

## 1. Principles & Quality Gates

1. **Black-Box System Boundary:** Specify what the system performs externally (observable inputs, responses, and state modifications), omitting private internal classes.
2. **Sea-Level Scoping (User Goal):** Must satisfy the *Coffee Break Test*: an elementary workflow performed in a single session by a primary actor delivering distinct business value.
3. **Decomposition:**
   * Main Success Scenario (Basic Flow).
   * Extension / Alternate Flows (numbered e.g. `3a`, `4b`).
   * Formal Pre-conditions and Post-conditions.

---

## 2. Inventory Index

| ID | Title | Status | Date | Primary Actor |
| :---: | :--- | :---: | :---: | :--- |
| **UC-01** | [UC-01: Dispatch Resilient HTTP Request](0001_dispatch_resilient_http_request.md) | **approved** | 2026-10-28 | Downstream Integration Client (`ed-capi`, `ed-eddn`, `ed-connectors`, `ed-state`) |
| **UC-02** | [UC-02: Spool and Drain Offline Telemetry Requests](0002_spool_and_drain_offline_telemetry_requests.md) | **approved** | 2026-10-28 | Downstream Egress Client (`ed-eddn`, `ed-connectors`) |
| **UC-03** | [UC-03: Consume Telemetry Stream and Local Daemon IPC](0003_consume_telemetry_stream_and_ipc.md) | **approved** | 2026-10-28 | Downstream Consumer (`ed-state`, `ed-connectors`, `ed-cli`) |
