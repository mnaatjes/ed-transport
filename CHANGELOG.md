# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-10-28

### Added
- Initial project architecture scaffolding adhering to pure Hexagonal Architecture (Ports and Adapters).
- Core domain entity and port contracts for bidirectional resilient HTTP transport and telemetry delivery.
- Comprehensive Unified Process specifications: Use cases (UC-01, UC-02, UC-03, UC-04) and Master Risk Register.
- Deterministic architectural boundary verification using `import-linter`, `pytest-archon`, `ruff`, and `mypy`.
- Automated versioning configuration using `bump-my-version`.
