# ed-transport

[![Version](https://img.shields.io/badge/version-v0.1.0-blue.svg)](CHANGELOG.md)

Resilient Hexagonal HTTP transport and telemetry delivery engine for Elite Dangerous


## Architectural Governance
This service is architected in accordance with Hexagonal Architecture (Ports and Adapters).
* Core Domain logic resides in `src/ed_transport/core/` with ZERO external infrastructure dependencies.
* Architectural boundaries are enforced deterministically via `import-linter` and `pytest-archon`.

## Quickstart

Run quality verification gates:
```bash
uv run python scripts/verify.py
```
