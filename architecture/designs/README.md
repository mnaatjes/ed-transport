---
title: "Software Design Documents Governance and Index"
tags: ["architecture", "designs", "sdd", "governance"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# Software Design Documents Governance and Index

Governed by IEEE 1016-2009 (Standard for Information Technology—Systems Design—Software Design Descriptions) and Google Design Doc standards.

---

## 1. Principles & Quality Gates

1. **Pre-Implementation Requirement:** An SDD must be drafted, reviewed, and approved before writing non-trivial production code.
2. **The Vacation Test:** The technical specification must be sufficiently complete that an independent engineer could implement, test, and deploy the subsystem without consulting the original author.
3. **The Skeptic Test:** The introduction must rigorously justify why the subsystem is being built and why simpler alternatives are insufficient.
4. **Mandatory Visual Models:** Incorporate at least two visual Mermaid diagrams (Structural Component model and Dynamic Flow model).

---

## 2. Design Documents Index

| Number | Title | Status | Date | Primary Author |
| :---: | :--- | :---: | :---: | :--- |
| **SDD-001** | [SDD-001: Scope and Boundary Enforcement Architecture](0001_scope_and_boundary_enforcement_architecture.md) | **approved** | 2026-10-28 | @mnaatjes |
| **SDD-002** | [SDD-002: TransportClient Driving Facade Implementation Architecture](0002_transport_client_driving_facade_architecture.md) | **draft** | 2026-10-28 | @mnaatjes |
| **SDD-003** | [SDD-003: Shared Library Logging and AST Boundary Enforcement Architecture](0003_shared_library_logging_enforcement_architecture.md) | **draft** | 2026-10-28 | @mnaatjes |
