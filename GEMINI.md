# Context & Developer Environment Guide: `ed-transport`

## 1. Project Overview & Architecture
`ed-transport` is a pure Hexagonal Architecture (Ports and Adapters) resilient HTTP transport and telemetry delivery engine for the *Elite Dangerous* software fleet, supporting Linux (Steam / Proton / Steam Deck) and native Windows NT.

It acts as the shared foundation library for `ed-capi`, `ed-eddn`, and `ed-connectors`, handling:
* Bidirectional resilient HTTP dispatch (`GET`, `POST`, `PUT`, `DELETE`).
* Destination-specific rate-limiting (token bucket & sliding window).
* Credential injection (Bearer tokens, API keys, Pre-shared tokens).
* Retries with exponential backoff and randomized decorrelated jitter.
* Offline bounded request spooling with pluggable storage.
* Local daemon IPC via chunked Server-Sent Events (SSE) with automated watchdog reconnection.

### Architectural Layout (`src/ed_transport/`)
- `src/ed_transport/core/domain/`: Pure domain core entities (`HttpRequest`, `HttpResponse`, `RetryPolicy`, `RateLimitRule`). Zero imports of external HTTP engines, frameworks, or operating system constructs.
- `src/ed_transport/core/ports/`: Domain boundary contracts:
  - `driving/`: Primary ports exposed to consumer applications (`HttpTransportPort`, `TelemetryStreamPort`, `SpoolManagerPort`).
  - `driven/`: Secondary SPIs implemented by adapters (`HttpEnginePort`, `CredentialProviderPort`, `RateLimiterPort`, `SpoolStoragePort`).
- `src/ed_transport/core/use_cases/`: Stateless use case interactors (`ExecuteHttpRequestUseCase`, `ConsumeTelemetryStreamUseCase`, `DrainSpoolBufferUseCase`).
- `src/ed_transport/adapters/`:
  - `driving/`: Programmatic client facades consumed by client libraries (`TransportClient`) and optional diagnostic CLI probes.
  - `driven/`: Concrete implementations (`engine/` for HTTP socket dispatch, `auth/` for credentials, `rate_limit/` for token buckets, `spool/` for circular buffers).
- `src/ed_transport/bootstrap/`: Composition root (`Container`, `create_transport_client`) wiring ports, interactors, and adapters.

---

## 2. Python Virtual Environment & Tooling Paths

The project uses a local virtual environment located at `.venv/` in the repository root:

* **Python Interpreter:** `.venv/bin/python`
* **Pytest:** `.venv/bin/pytest`
* **Ruff (Linter & Formatter):** `.venv/bin/ruff`
* **Import Linter:** `.venv/bin/lint-imports`
* **Type Checker:** `.venv/bin/mypy`

> [!IMPORTANT]
> Always execute commands and tests directly using `.venv/bin/<tool>` (e.g. `.venv/bin/python scripts/verify.py` or `.venv/bin/pytest`).

---

## 3. Standard Verification Commands

All changes must pass Tier 2 Quality Gates:

```bash
# 1. Complete Tier 2 Quality Gates (Pre-commit, Ruff lint/format, Import linter, MyPy, Pytest suite):
.venv/bin/python scripts/verify.py

# 2. Targeted Unit Tests:
.venv/bin/pytest tests/architecture/test_boundaries.py

# 3. Import Boundary Linter (verifies Hexagonal isolation invariants):
.venv/bin/lint-imports

# 4. Local Wine Windows NT Simulation (cross-platform verification):
./scripts/run_wine_tests.sh
```

---

## 4. Context Hydration & Traceability

* **Parent Architectural Specification:** [ed-telemetry ADR 0035: Integration Fleet Decomposition and Boundary Taxonomy](file:///home/michael/src/github.com/mnaatjes/ed-telemetry/architecture/adr/0035_integration_fleet_decomposition_and_boundary_taxonomy.md)
* **Governing Template:** [python-hexagonal-template](https://github.com/mnaatjes/python-hexagonal-template.git)
* **Unified Process Documentation:**
  * Master Risk Register: `architecture/risk/risk-list.md`
  * Use-Case Specifications: `architecture/use-cases/` (`UC-01`, `UC-02`, `UC-03`)
  * Empirical Protocol Research: `architecture/research/`
  * Architectural Decision Records: `architecture/adr/`
  * Software Design Documents: `architecture/designs/`
* **Conversation ID:** `f168e79f-2cab-4b17-9ef2-607df09b9ede`
