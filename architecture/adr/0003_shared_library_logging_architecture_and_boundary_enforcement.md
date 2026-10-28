---
title: "ADR 0003: Shared Library Logging Architecture and Boundary Enforcement"
status: "accepted"
date: "2026-10-28"
deciders: ["Core Architecture Team"]
consulted: ["ADR 0001", "ADR 0002", "PEP 2818", "Python Logging Tutorial for Library Developers"]
informed: ["All Engineers", "Downstream Consumer Authors (ed-capi, ed-eddn, ed-connectors, ed-telemetry)"]
tags: ["adr", "architecture", "logging", "shared-library", "null-handler", "boundary-enforcement"]
---

# ADR 0003: Shared Library Logging Architecture and Boundary Enforcement

## Context and Problem Statement

`ed-transport` is architected as an internal shared library foundation rather than a standalone executable or daemon. In Python systems, libraries and host applications operate under distinct lifecycle and operational boundaries.

When libraries improperly attempt to configure logging:
1. They interfere with host application logging pipelines by injecting unwanted handlers, formatting rules, or modifying root logger thresholds (`logging.basicConfig()`).
2. They risk emitting noisy `No handlers could be found for logger "ed_transport"` warnings or directing raw unformatted log records to `sys.stderr` via `logging.lastResort` when consumers have not configured logging.
3. They introduce unwanted coupling to external opinionated logging frameworks (e.g. Loguru, Structlog, Rich) or enforce filesystem path assumptions for log sinks.

How must `ed-transport` structure its logging emission, handler binding, and boundary enforcement to remain completely transparent, non-intrusive, and compliant with PEP 2818 and Hexagonal Architecture?

---

## Decision Drivers

* **PEP 2818 & Python Standard Library Compliance:** Adhere strictly to canonical Python shared library logging conventions.
* **Host Application Sovereignty:** Consuming applications (`ed-capi`, `ed-eddn`, `ed-connectors`, `ed-telemetry`) must retain exclusive ownership over log destinations, formatting, filtering, and retention.
* **Silent Fallback:** Library logging must remain completely silent and raise zero warnings or stderr pollution when consumed in minimal scripts or unit test suites without configured handlers.
* **Automated Mechanical Enforcement:** Architectural boundaries must be statically enforced through automated AST test suites (`tests/architecture/test_boundaries.py`) to prevent regressions during future development.

---

## Considered Options

* **Option 1: Opinionated Logging Framework.** Adopt an external structured logging framework (such as Structlog or Loguru) across the library. *(Rejected: Forces heavy external dependencies on consumers, creates conflicting runtime logging loops, and violates library boundary decoupling)*.
* **Option 2: Direct Stderr Logging or Custom Handlers.** Configure internal console or file handlers within `ed-transport`. *(Rejected: Completely violates library hygiene; pollutes consumer console output and makes unauthorized filesystem assumptions)*.
* **Option 3: Standard Library Logging with Package Root `NullHandler` and Strict Boundary Linting.** Emit log records strictly via standard library `logging.getLogger(__name__)`, attach a `logging.NullHandler()` at the `ed_transport` package root, and mechanically forbid all handler, level, and sink configurations via AST checks.

---

## Decision Outcome

Chosen Option: **Option 3: Standard Library Logging with Package Root `NullHandler` and Strict Boundary Linting**.

### 1. The `logging.NullHandler` Silent Absorption Mechanism

In accordance with PEP 2818, `src/ed_transport/__init__.py` attaches a `logging.NullHandler()` directly to the top-level `"ed_transport"` logger:

```python
import logging

logging.getLogger("ed_transport").addHandler(logging.NullHandler())
```

* `logging.NullHandler` acts as a dummy, no-op handler that absorbs and discards all log records silently if no parent handler is configured by the consuming host application.
* When a host application configures logging (e.g., via `logging.basicConfig()` or custom log handlers), Python's logger hierarchy naturally propagates records from `ed_transport.*` up to the host's configured handlers without interference.

### 2. Core Canonical Logging Conventions

Every module in `ed-transport` must strictly follow these five conventions:

1. **Be Quiet by Default (`NullHandler`):**
   * Attach `logging.NullHandler()` at library root (`src/ed_transport/__init__.py`). If the caller hasn't set up logs, stay silent. Never print unformatted warnings to `sys.stderr`.
2. **Name Your Loggers (`__name__`):**
   * Always instantiate loggers with `logger = logging.getLogger(__name__)`. Modules are clearly identified (e.g. `ed_transport.adapters.driving.client`).
3. **Hands Off the Steering Wheel (No `basicConfig`):**
   * Never call `logging.basicConfig()`. The host application owns process-wide configuration.
4. **No Real Destinations (No Sinks/Handlers):**
   * Never attach real outputs (files, stdout, sockets) inside the library. The host application decides where records go.
5. **Lazy Formatting (No f-strings):**
   * Always write `logger.debug("Dispatching to %s", url)`, never `logger.debug(f"Dispatching to {url}")`. Lazy formatting avoids building strings when debug mode is disabled.

### 3. Internal Emission Rules

All modules within `src/ed_transport/` must adhere strictly to the following emission pattern:

```python
import logging

logger = logging.getLogger(__name__)

# Usage:
logger.debug("Dispatching HTTP %s request to %s", method, url)
logger.warning("Spool buffer capacity reached %d bytes; dropping oldest payload", current_bytes)
```

---

## Explicit Out-of-Scope Boundaries for `ed-transport`

The following logging responsibilities belong exclusively to host applications and are strictly **out-of-scope** for `ed-transport`:

1. **Log Sinks and Handlers Configuration:**
   * Adding `logging.StreamHandler`, `FileHandler`, `SysLogHandler`, or socket sinks.
   * Determining destination log file paths or creating logging directories on the filesystem.
2. **Log Levels and Filtering Policies:**
   * Setting root or namespace log thresholds (`logger.setLevel(...)`).
   * Filtering logs based on host application runtime environments (development vs production vs debug).
3. **Log Formatting and Serialization:**
   * Applying text formatting strings (`"%(asctime)s - %(levelname)s - %(message)s"`).
   * Configuring JSON, Logfmt, or structured serialization formatters.
4. **Log Rotation and Retention Management:**
   * Size-based (`RotatingFileHandler`) or time-based (`TimedRotatingFileHandler`) log file rotation.
   * Compression, archiving, pruning, or disk retention quotas for log files.
5. **Third-Party Logging Framework Opinions:**
   * Declaring dependencies on or initializing external logging engines (`loguru`, `structlog`, `rich.logging`, `sentry_sdk`, OpenTelemetry loggers).
6. **Process-Wide Logging Initialization:**
   * Invoking `logging.basicConfig()` or mutating existing parent logger handlers in the host process.

---

## Driving Facade Impact and Parameter Surface

The driving adapter facades (`TransportClient` and `AsyncTransportClient`) in `src/ed_transport/adapters/driving/client.py` strictly preserve shared library logging boundaries:

1. **Zero Logging Configuration Parameters:**
   * The constructors of `TransportClient` and `AsyncTransportClient` **do not accept** logging parameters (e.g. `logger`, `log_level`, `log_format`, or `log_handler`).
   * Rationale: Inversion of logging control must be handled via Python's standard `logging` hierarchy (`logging.getLogger("ed_transport")`), not by injecting logging objects or setting log levels via client constructor parameters.
2. **Transparent Module-Level Logger Emission:**
   * The facades instantiate their own private, namespaced module logger:
     ```python
     logger = logging.getLogger(__name__)  # ed_transport.adapters.driving.client
     ```
   * Lifecycle actions (client initialization, context entry, client close) and facade dispatch attempts emit events at `DEBUG` level to this logger without altering or exposing logger state to the consumer.

---

## Opt-In Fleet Logging Bootstrap Factory

To eliminate code duplication across fleet daemons (`ed-capi`, `ed-eddn`, `ed-connectors`) while strictly preserving the "No Real Destinations" library rule, `ed-transport` provides an **opt-in helper factory** in `src/ed_transport/bootstrap/logging.py`:

```python
def configure_fleet_logging(
    app_name: str,
    log_dir: Path | None = None,
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 5,
) -> Path:
    """Configures standardized rotating file logging for fleet daemon applications."""
```

### Architectural Guarantees:
* **Zero Automatic Execution:** Importing `ed-transport` never invokes this helper. It must be explicitly called by the daemon's CLI entrypoint or `main()`.
* **Standard Platform Directories:**
  * Linux / Steam Deck: `~/.local/state/<app_name>/logs/<app_name>.log`
  * Windows NT: `%LOCALAPPDATA%\<app_name>\logs\<app_name>.log`
* **Safe Log Rotation:** Implements `RotatingFileHandler` with a strict size cap (default: 5 files × 5 MB = 25 MB max disk usage). Old logs are pruned automatically.

---

## Mechanical Boundary Enforcement Mechanisms

To guarantee that `ed-transport` never violates these boundaries, `tests/architecture/test_boundaries.py` implements automated AST inspection over all source files in `src/ed_transport/`:

1. **Forbid `logging.basicConfig`:** Scans all AST `Call` nodes; asserts that `logging.basicConfig` is never invoked anywhere in the codebase.
2. **Restrict `addHandler` Calls:** Asserts that `.addHandler()` is called only in two sanctioned bootstrap locations:
   * `src/ed_transport/__init__.py`: Binding `NullHandler()` to the root `"ed_transport"` logger.
   * `src/ed_transport/bootstrap/logging.py`: Binding `RotatingFileHandler()` inside the opt-in `configure_fleet_logging` factory function.
3. **Forbid In-Code `setLevel` Mutation:** Asserts that `.setLevel()` is never invoked within library core or adapter modules (only permitted inside the opt-in `bootstrap/logging.py` factory).
4. **Restrict Concrete Handlers & Formatters:** Asserts that `RotatingFileHandler`, `StreamHandler`, and `Formatter` are never imported outside `src/ed_transport/bootstrap/logging.py`.
5. **Forbid Third-Party Logging Engines:** Asserts that third-party logging modules (`loguru`, `structlog`, `rich.logging`, `sentry_sdk`) are never imported anywhere.
6. **Forbid Formatter Instantiation in Core/Adapters:** Asserts that `logging.Formatter` is never instantiated outside `src/ed_transport/bootstrap/logging.py`.
7. **Forbid f-strings in Logger Calls:** Scans AST `Call` nodes for logger methods (`debug`, `info`, `warning`, `error`, `critical`); asserts that the first argument is not an `ast.JoinedStr` (f-string) to strictly enforce lazy string interpolation across all modules.

---

## Consequences

### Positive
* Zero friction for consuming applications: Host apps maintain total control over log output, sinks, formatting, and verbosity.
* Clean, silent execution when running tests or CLI utilities without configured logging.
* Strict architectural invariants are mechanically verified on every commit and pull request.
* Zero third-party dependency bloat.

### Expected Maintenance Costs (Design Trade-offs)
* `ed-transport` cannot output diagnostic logs to the console "out of the box" unless the calling application configures a handler.
* Developers authoring tests must explicitly attach a handler (e.g. pytest's `caplog` fixture) when verifying emitted log messages.

---

## Documentation Impact and Required Updates

Upon implementation of this ADR, the following documentation must be updated or authored:

1. **New How-To Guide (`docs/how-to/configure_fleet_logging.md`):**
   * Provide step-by-step instructions for daemon applications (`ed-capi`, `ed-eddn`, `ed-connectors`) to call `configure_fleet_logging()`.
   * Document platform directory paths (Linux `~/.local/state/` vs Windows `%LOCALAPPDATA%`), log rotation behavior (5 files × 5 MB), and log level overrides.
2. **Update API Reference (`docs/reference/transport_client.md`):**
   * Add `ed_transport.bootstrap.logging` exports (`configure_fleet_logging`, `get_platform_log_dir`).
   * Explicitly document that `TransportClient` and `AsyncTransportClient` adhere to library logging semantics (zero log parameters, silent `NullHandler` root absorption).
