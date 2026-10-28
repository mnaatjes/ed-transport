---
title: "Downstream Hexagonal Invariants Directives"
type: "system_rule"
status: "active"
trigger: "code_generation"
description: "Directs coding agents to strictly uphold Hexagonal Architecture boundaries and invariants."
created_at: "2026-10-12"
last_updated_at: "2026-10-12"
---

# Downstream Hexagonal Invariants Directives

When authoring or modifying code within this service, coding assistants must strictly preserve the following architectural truths:

## HEXA-TRUTH-01: Pure Core Domain Isolation
* Never import adapters, databases, HTTP clients, or external frameworks inside `core/domain/`.
* All logic within `core/domain/` must remain pure Python.

## HEXA-TRUTH-02: Inward Dependency Direction
* Outer adapters (`adapters/`) may depend on inner ports (`core/ports/`).
* Inner ports and domain logic must never import adapters or external layers.

## HEXA-TRUTH-03: Port Abstraction & Protocol Integrity
* Every port declared in `core/ports/` must be an abstract interface: use `typing.Protocol` with `@typing.runtime_checkable` or `abc.ABC` with `@abc.abstractmethod`.
* Never declare concrete port classes, functions, or import infrastructure/transport types (e.g. `Request`, `Session`) in port interfaces.

## HEXA-TRUTH-04: DTO & Anti-Tunneling Boundary Purity
* Port method parameters and return types must be pure immutable DTOs, frozen dataclasses, or primitives.
* Never pass ORM models, framework payloads, or raw mutable entities directly across port interfaces.

## HEXA-TRUTH-05: Zero Lifecycle Pollution in Domain
* Never instantiate threads, process workers, or event loops (`asyncio.run()`, `threading.Thread`) inside `core/domain/` or `core/use_cases/`.
* Lifecycles, daemon loops, and signal handling belong strictly in driving adapters or bootstrap entrypoints.

## HEXA-TRUTH-06: Domain-to-Port Isolation
* Never import `core/ports/` or `core/use_cases/` inside `core/domain/`. Domain entities exist independently of port abstractions and use case interactors.

## HEXA-TRUTH-07: Business Exception Sovereignty
* All business exceptions must inherit from `DomainError` in `core/domain/exceptions.py`. Never catch or raise infrastructure errors in domain models.

## HEXA-TRUTH-08: Zero Global Mutable State in Domain
* Never declare mutable module-level variables (lists, dicts, sets, caches) in `core/domain/`.

## HEXA-TRUTH-09: Pure In-Memory Determinism
* Domain entities and functions must be deterministic; never access `os.environ` or ambient system state directly. Pass context as function arguments.

## HEXA-TRUTH-10: Self-Validating Entity Invariants
* Domain models must enforce validity at instantiation using `@dataclass(frozen=True)` or validation checks.

## HEXA-TRUTH-11: Lexical & Structural Use Case Invariants
* Name use case classes as `^[A-Z][a-zA-Z0-9]+UseCase$` starting with an imperative verb (`Check`, `Get`, `Create`, `Process`).
* Always define constructor dependency injection in `__init__`.

## HEXA-TRUTH-12: Inversion of Control & Zero Concrete Instantiation
* Never instantiate or import concrete adapters inside use cases. Dependencies must be injected as abstract driven ports.

## HEXA-TRUTH-13: Transport & Framework Agnosticism in Use Cases
* Never import web frameworks (`fastapi`, `flask`), CLI libraries (`typer`, `click`), or transport exceptions inside use cases.

## HEXA-TRUTH-14: Stateless Interactor Invariants
* Use cases must be stateless. Never assign or mutate `self.*` attributes outside `__init__`.

## HEXA-TRUTH-15: Zero Direct I/O Bypass
* Never execute direct network calls (`requests`, `httpx`) or raw I/O in use cases. Route all side effects through Driven Ports.

## HEXA-TRUTH-16: Zero Implementation Code in Ports
* Port method bodies must contain strictly `...` or `pass`. Never declare `__init__`, concrete state, or logic in ports.

## HEXA-TRUTH-17: Technology-Agnostic Port Nomenclature
* Name port classes ending with `Port`. Never include technology names (`Sql`, `Http`, `Redis`, `Mongo`) in port class names.

## HEXA-TRUTH-18: Strict Port Package Import Whitelist
* Port files must only import from `typing`, `abc`, `collections.abc`, standard primitives, and `core.domain`.

## HEXA-TRUTH-19: Composition Root Isolation
* Core layers (`core/domain/`, `core/ports/`, `core/use_cases/`) and adapters (`adapters/`) must never import from `bootstrap/`.
* The composition root (`bootstrap/container.py`) is the sole structural authority for instantiating adapters and wiring dependencies into use cases.

## HEXA-TRUTH-20: Driving Port Directional Integrity & Use Case Exclusivity
* Driving ports must reside in `core/ports/driving/` and inherit from `DrivingPort`.
* Driving ports are implemented strictly by application use cases (`core/use_cases/`). Adapters must never implement driving ports.

## HEXA-TRUTH-21: Driven Port Inversion & Injection Governance
* Driven ports must reside in `core/ports/driven/` and inherit from `DrivenPort`.
* Driven ports are implemented strictly by driven adapters (`adapters/driven/`). Use cases must accept driven ports via constructor dependency injection (`__init__`) and never implement them.

## HEXA-TRUTH-22: Repository vs. Recipient Driven Port Semantics
* Classify driven ports as Repositories (state retrieval/persistence) or Recipients (fire-and-forget notifications returning `None`). Never conflate both in one interface.

## HEXA-TRUTH-23: Outbound Infrastructure Exception Masking
* Driven adapters must catch external vendor exceptions (`psycopg2`, `redis`, `boto3`, `OSError`) and translate them into domain port exceptions.

## HEXA-TRUTH-24: Driven Port Return Type Encapsulation
* Driven port methods must return domain models, value objects, or frozen DTOs. Never return ORM querysets, raw database cursors, or untyped dicts.

## HEXA-TRUTH-25: Driving Port CQRS & Use Case Cohesion
* Driving ports represent cohesive business capabilities. Never expose persistence CRUD verbs (`save`, `delete`, `find_by_id`, `update_row`).

## HEXA-TRUTH-26: Caller & Transport Ignorance in Driving Signatures
* Driving port parameters must never accept transport-specific objects (`Request`, `Response`, `Header`, `Session`, `CliContext`). Use pure primitives or frozen DTOs.

## HEXA-TRUTH-27: Dual-Adapter Test Double Parity
* Maintain an in-memory test double in `tests/doubles/` for every driven port in `core/ports/driven/` to guarantee offline testability.

## HEXA-TRUTH-28: DTO Immutability & Structural Purity
* Co-locate DTOs inside `core/ports/driving/` or `core/ports/driven/`. Never place DTOs in `adapters/` or `core/domain/`.
* Decorate all DTOs with `@dataclass(frozen=True, slots=True)` or inherit `DataTransferObject`.
* Restrict field types strictly to primitives, frozen DTOs, tuples, frozensets, and domain value objects. Never use mutable lists/dicts or ORM/framework models.
