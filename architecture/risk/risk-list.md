---
title: "Master Risk Register"
tags: ["architecture", "risk", "register"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# Master Risk Register

Barry Boehm Risk Exposure ($RE = P \times I$) log and Environmental/Technical boundary definitions for the `ed-transport` project lifecycle.

---

## 1. Environmental and Technical Boundaries

The operational envelope of `ed-transport` is bounded by the following environmental realities:

* **Host Networking Environments:** Must support native Linux (desktop / headless server), Linux Steam Deck (Proton / Steam runtime), and native Windows 10/11 environments.
* **Socket Concurrency Constraints:** Must run safely within single-threaded reactive loops or multi-threaded background workers without triggering thread-safety deadlocks or socket descriptor leaks.
* **Third-Party Quotas:** Must adapt to differing upstream API rate limits:
  * *EDDN:* Uncapped public ingestion, but sensitive to high-frequency connection thrashing (requires persistent connection pooling).
  * *Frontier CAPI:* Highly sensitive to burst traffic; violations risk IP-level or account-level cooldown blocks.
  * *Inara / EDSM:* Enforces discrete batch limits and daily developer call ceilings.
* **Storage Footprint Limits:** Offline in-memory spools must be strictly bounded ($\le 10 \text{ MB}$ default memory ceiling) to prevent starving low-memory host systems.
* **Telemetry Server Perimeter:** Must communicate seamlessly with `ed-telemetry` over local HTTP/SSE while respecting authentication boundaries (pre-shared key header injection).

---

## 2. Active Risk Log

| Risk ID | Title / Risk Description | Probability ($P$) | Impact ($I$) | Exposure ($RE$) | Status | Mitigation Strategy |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **RISK-01** | **Downstream API Rate Limiting / 429 Cascades:** Rapid bursts of telemetry events overwhelm third-party rate limits (Inara/EDSM/Frontier), resulting in temporary IP bans or dropped data. | 4 | 4 | **16** | active | Implement token-bucket and sliding-window rate limiters within `ed-transport` with per-destination quotas and exponential backoff with decorrelated jitter. |
| **RISK-02** | **Socket Stalls & Hangs:** External servers accept connections but hang indefinitely during transfer, starving client worker threads. | 3 | 4 | **12** | active | Enforce strict connect, read, and write timeouts across all HTTP engine adapters with non-blocking async and thread-pool execution. |
| **RISK-03** | **Unbounded Offline Buffer Growth:** Network connectivity loss causes offline queue spooling to consume excessive host RAM. | 3 | 3 | **9** | active | Implement bounded in-memory circular buffers with optional persistent disk-backed spooling and explicit capacity ceilings. |
| **RISK-04** | **Credential Exposure in Logs:** Transport debugging inadvertently logs HTTP Authorization headers or API keys in plain text. | 3 | 4 | **12** | active | Author dedicated redacting logging filters in transport pipelines that sanitize Bearer tokens and sensitive header values before emission. |
| **RISK-05** | **HTTP Engine Library Dependency Lock-in:** Direct coupling to a specific external HTTP library (`httpx` or `requests`) prevents swapping implementations if dependency conflicts occur in client apps. | 3 | 3 | **9** | active | Hexagonal isolation: declare an abstract `HttpEnginePort` protocol, keeping third-party HTTP libraries confined strictly to driven adapters. |
| **RISK-06** | **Embedded System Clock Skew & TLS Verification:** Proton/Wine or Steam Deck environments with skewed local system clocks fail TLS certificate validation on HTTPS handshakes. | 2 | 4 | **8** | active | Ensure descriptive error diagnostics when SSLError/CertificateError is caught, identifying system clock drift as a primary cause. |
| **RISK-07** | **Async/Sync Concurrency & Event-Loop Deadlocks:** Client applications invoking `ed-transport` from within active `asyncio` event loops experience deadlocks if transport uses blocking synchronous sleep. | 3 | 4 | **12** | active | Provide clean asynchronous execution paths (`AsyncTransportPort`) alongside thread-safe synchronous facades (`TransportPort`), avoiding `asyncio.run()` inside running loops. |
| **RISK-08** | **Token Leakage in URLs, Headers, and Traces:** Dynamic credentials (such as `ED_API_KEY`, Inara API keys, or Frontier tokens) leak via query strings or unhandled exception tracebacks. | 3 | 5 | **15** | active | Enforce token masking interceptors; reject API keys passed via URL query parameters in favor of Authorization headers; strip sensitive headers from exception error payloads. |
| **RISK-09** | **Cross-Platform Socket Errors & Windows NT Discrepancies:** Differences between POSIX socket errnos and Windows `WSA*` error codes cause unhandled failures during network dropouts on Windows. | 3 | 4 | **12** | active | Normalize network socket exceptions in driven adapters; establish local Wine test simulation (`scripts/run_wine_tests.sh`) and multi-platform CI matrices. |
