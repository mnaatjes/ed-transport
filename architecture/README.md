---
title: "Architecture Directory Governance and Contract"
tags: ["architecture", "governance", "up"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# Architecture Directory Governance and Contract

This directory serves as the authoritative Single Source of Truth (SSoT) for internal technical governance, requirements specifications, architectural trade-offs, and implementation blueprints for the `ed-transport` project under the Unified Process (UP).

---

## 1. Dual-Root Partition

* **Maintainer / Engineering Plane (`architecture/`):** Reserved exclusively for internal engineering ledgers, formal requirements, design documents, and decision records.
* **Customer / Operator Plane (`docs/`):** Reserved exclusively for living, mutable user-facing manuals and runbooks governed by the Diátaxis framework.

---

## 2. Retained Architectural Document Types & Taxonomy

```text
architecture/
|-- README.md                      # Directory contract & governance index (this document)
|-- risk/                          # Project Management Discipline (Master Risk Register)
|-- use-cases/                     # Requirements Discipline (RUP Use-Case Specifications)
|-- research/                      # Platform & Protocol Empirical Research Ledger
|-- adr/                           # Analysis & Design Discipline (MADR 3.0 Decision Records)
|-- designs/                       # Analysis & Design / Implementation (IEEE 1016 SDDs)
|-- rfcs/                          # Requirements & Architectural Consensus Proposals
\-- api/                           # Interface & Boundary Contract Specifications
```
