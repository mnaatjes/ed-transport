---
title: "Master Risk Register"
tags: ["architecture", "risk", "register"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# Master Risk Register

Barry Boehm Risk Exposure ($RE = P \times I$) log for the `ed-transport` project lifecycle.

---

## Active Risk Log

| Risk ID | Title / Risk Description | Probability ($P$) | Impact ($I$) | Exposure ($RE$) | Status | Mitigation Strategy |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **RISK-01** | **Downstream API Rate Limiting / 429 Cascades:** Rapid bursts of telemetry events overwhelm third-party rate limits (e.g. Inara/EDSM/Frontier), resulting in temporary IP bans or dropped data. | 4 | 4 | **16** | active | Implement token-bucket and sliding-window rate limiters within `ed-transport` with per-destination quotas and exponential backoff with decorrelated jitter. |
| **RISK-02** | **Socket Stalls & Hangs:** External servers accept connections but hang indefinitely during transfer, starving client worker threads. | 3 | 4 | **12** | active | Enforce strict connect, read, and write timeouts across all HTTP engine adapters with non-blocking async and thread-pool execution. |
| **RISK-03** | **Unbounded Offline Buffer Growth:** Network connectivity loss causes offline queue spooling to consume excessive host RAM. | 3 | 3 | **9** | active | Implement bounded in-memory circular buffers with optional persistent disk-backed spooling and explicit capacity ceilings. |
| **RISK-04** | **Credential Exposure in Logs:** Transport debugging inadvertently logs HTTP Authorization headers or API keys in plain text. | 3 | 4 | **12** | active | Author dedicated redacting logging filters in transport pipelines that sanitize Bearer tokens and sensitive header values before emission. |
