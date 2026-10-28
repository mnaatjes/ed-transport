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

### 2. Internal Emission Rules

All modules within `src/ed_transport/` must adhere strictly to the following emission pattern:

```python
import logging

logger = logging.getLogger(__name__)

# Usage:
logger.debug("Dispatching HTTP %s request to %s", method, url)
logger.warning("Spool buffer capacity reached %d bytes; dropping oldest payload", current_bytes)
```

* Loggers must be instantiated at module scope using `logging.getLogger(__name__)`.
* String formatting must rely on lazy logger interpolation (`logger.debug("msg %s", arg)`), never pre-formatted f-strings, to avoid performance overhead when the log level is disabled.

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

## Mechanical Boundary Enforcement Mechanisms

To guarantee that `ed-transport` never violates these boundaries, `tests/architecture/test_boundaries.py` implements automated AST inspection over all source files in `src/ed_transport/`:

1. **Forbid `logging.basicConfig`:** Scans all AST `Call` nodes; asserts that `logging.basicConfig` is never invoked anywhere in the codebase.
2. **Forbid Unauthorized `addHandler` Calls:** Asserts that `.addHandler()` is called at most once across the entire codebase, and only within `src/ed_transport/__init__.py` passing an instance of `logging.NullHandler`.
3. **Forbid In-Code `setLevel` Mutation:** Asserts that `.setLevel()` is never invoked on any logger within library source files.
4. **Forbid Concrete Handler Instantiation & Imports:** Asserts that forbidden standard library handlers (`StreamHandler`, `FileHandler`, `RotatingFileHandler`, `TimedRotatingFileHandler`, `SysLogHandler`, `SocketHandler`, `MemoryHandler`, `HTTPHandler`) are never imported or instantiated.
5. **Forbid Third-Party Logging Engines:** Asserts that third-party logging modules (`loguru`, `structlog`, `rich.logging`, `sentry_sdk`) are never imported.
6. **Forbid Formatter Instantiation:** Asserts that `logging.Formatter` is never instantiated or assigned within library code.

---

## Consequences

### Positive
* Zero friction for consuming applications: Host apps maintain total control over log output, sinks, formatting, and verbosity.
* Clean, silent execution when running tests or CLI utilities without configured logging.
* Strict architectural invariants are mechanically verified on every commit and pull request.
* Zero third-party dependency bloat.

### Negative / Trade-offs
* `ed-transport` cannot output diagnostic logs to the console "out of the box" unless the calling application configures a handler.
* Developers authoring tests must explicitly attach a handler (e.g. pytest's `caplog` fixture) when verifying emitted log messages.
