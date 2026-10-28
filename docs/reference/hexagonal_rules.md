---
title: "Hexagonal Architecture Invariant Rules"
tags: ["hexagonal-architecture", "reference", "invariants"]
created_at: "2026-10-12"
last_updated_at: "2026-10-12"
---

# Hexagonal Architecture Invariant Rules

This reference documents the governing architectural invariants ("Truths") enforced across the service codebase. Every truth is mechanically enforced via static linters, AST checks, and unit test suites.

---

### HEXA-TRUTH-01: Pure Core Domain Isolation

* **Definition:** The core domain (`core/domain/`) represents pure business entities, value objects, and domain logic. It must never import external infrastructure, database frameworks, web frameworks, or adapter implementations.
* **Enforcement:**
  * `.importlinter`: Contract `core_domain_isolation` forbids outer package imports.
  * `pytest-archon`: `test_core_domain_has_zero_external_dependencies`.
* **Remediation:** If the core domain requires external interaction, declare a port abstraction (`core/ports/`) and implement it in an adapter.

---

### HEXA-TRUTH-02: Inward Dependency Direction

* **Definition:** Dependencies must strictly flow inward: Driving and Driven Adapters depend on Application Ports; Application Services depend on Domain Entities. The domain and application core never depend on concrete adapters.
* **Enforcement:**
  * `.importlinter`: Contract `inward_dependency_direction` enforces layering hierarchy.
  * `pytest-archon`: `test_dependencies_point_strictly_inward`.
* **Remediation:** Invert the dependency by defining an interface in `core/ports/` and injecting the concrete adapter at runtime.

---

### HEXA-TRUTH-03: Port Abstraction & Protocol Integrity

* **Definition:** Ports defined under `core/ports/driving/` and `core/ports/driven/` must be abstract contracts (`typing.Protocol` with `@typing.runtime_checkable` or `abc.ABC`). Adapters satisfy port contracts without leaking transport, framework, or infrastructure types into method signatures.
* **Enforcement:**
  * `strict_typing`: `mypy --strict` enforcing structural or nominal type satisfaction.
  * `pytest-archon`: `test_ports_are_abstract_protocols_or_abcs`.
* **Remediation:** Refactor concrete port classes into `typing.Protocol` or `abc.ABC`, moving concrete implementations into `adapters/`.

---

### HEXA-TRUTH-04: DTO & Anti-Tunneling Boundary Purity

* **Definition:** Data crossing port boundaries (parameters and return types of port methods) must consist strictly of immutable DTOs, frozen dataclasses, standard library primitives, or pure domain value objects. Ports must never expose ORM database models, framework request/response objects, or mutable entities.
* **Enforcement:**
  * `pytest_archon`: `test_port_signatures_use_pure_dtos_and_primitives`.
  * `runtime_reflection`: Boundary introspection auditing runtime method annotations.
* **Remediation:** Map internal models or external payloads to dedicated frozen DTOs (`dataclasses.dataclass(frozen=True)`) before passing them across the port boundary.

---

### HEXA-TRUTH-05: Zero Lifecycle Pollution in Domain

* **Definition:** The domain and use case interactors represent pure business rules and data transformations. They must never control process lifecycles, instantiate background threads or worker loops, manage OS signal listeners, or invoke event loops (`asyncio.run()`). Lifecycles and thread management belong strictly to Driving Adapters, Driven Adapters, or Bootstrap entrypoints.
* **Enforcement:**
  * `pytest_archon`: `test_domain_and_use_cases_have_zero_lifecycle_pollution`.
* **Remediation:** Move event loops, concurrency management, and thread worker lifecycles into the driving adapter or composition root (`bootstrap/`).

---

### HEXA-TRUTH-06: Domain-to-Port Isolation

* **Definition:** The core domain (`core/domain/`) represents pure business entities and rules. It must never import `core/ports/` or `core/use_cases/`. Domain entities exist independently of port contracts or application orchestration.
* **Enforcement:**
  * `.importlinter`: Contract `domain_port_isolation` forbids importing ports or use cases inside domain.
  * `pytest_archon`: `test_domain_never_imports_ports_or_use_cases`.
* **Remediation:** Remove port or use case imports from domain entities. Use Cases must orchestrate ports and pass resulting data to domain entities, not vice versa.

---

### HEXA-TRUTH-07: Business Exception Sovereignty

* **Definition:** All business exceptions raised by the domain must inherit from a pure domain root (`core.domain.exceptions.DomainError`). The domain must never catch, inherit from, or re-raise transport-specific or third-party infrastructure exceptions.
* **Enforcement:**
  * `pytest_archon`: `test_domain_exceptions_inherit_from_domain_error`.
* **Remediation:** Define business errors under `core/domain/exceptions.py` inheriting from `DomainError`. Catch infrastructure exceptions in adapters and translate them into domain errors.

---

### HEXA-TRUTH-08: Zero Global Mutable State in Domain

* **Definition:** The core domain must remain pure and free from mutable global singletons, module-level caches, or mutable collections (`list`, `dict`, `set`) assigned at module root.
* **Enforcement:**
  * `pytest_archon`: `test_domain_has_zero_global_mutable_state`.
* **Remediation:** Encapsulate state inside immutable entity instances or value objects. Pass required context as explicit function arguments.

---

### HEXA-TRUTH-09: Pure In-Memory Determinism

* **Definition:** Domain logic and calculations must be deterministic pure functions of their inputs. The domain must never inspect ambient environment variables (`os.environ`) or read unparametrized system state.
* **Enforcement:**
  * `pytest_archon`: `test_domain_has_zero_ambient_environment_access`.
* **Remediation:** Read configuration in the driving adapter or bootstrap container, and pass explicit configuration values into domain constructors or use case methods.

---

### HEXA-TRUTH-10: Self-Validating Entity Invariants

* **Definition:** Domain entities and value objects must enforce their own validity at instantiation time (using `@dataclass(frozen=True)`, `StrEnum`, or `__post_init__` checks). An entity must never exist in an invalid or corrupted state.
* **Enforcement:**
  * `pytest_archon`: `test_domain_entities_are_self_validating`.
* **Remediation:** Add validation guards inside entity constructors or `__post_init__` methods that raise `DomainValidationError` when invariants are breached.

---

### HEXA-TRUTH-11: Lexical & Structural Use Case Invariants

* **Definition:** Every use case in `core/use_cases/` represents a discrete system operation. It must be authored as a class ending in `UseCase`, begin with an imperative verb (e.g. `Check`, `Get`, `Create`, `Process`), and declare constructor dependency injection via `__init__`.
* **Enforcement:**
  * `pytest_archon`: `test_use_cases_follow_lexical_and_structural_conventions`.
* **Remediation:** Rename the class to match `^[A-Z][a-zA-Z0-9]+UseCase$` with an active imperative verb prefix, and inject dependencies through `__init__`.

---

### HEXA-TRUTH-12: Inversion of Control & Zero Concrete Instantiation

* **Definition:** Use cases coordinate abstract driven ports. They must never import, reference, or instantiate concrete adapter classes directly inside their constructors or methods.
* **Enforcement:**
  * `pytest_archon`: `test_use_cases_do_not_instantiate_concrete_adapters`.
* **Remediation:** Declare an abstract port interface in `core/ports/driven/` and accept it as a typed constructor parameter.

---

### HEXA-TRUTH-13: Transport & Framework Agnosticism in Use Cases

* **Definition:** Use cases represent pure application workflows independent of external delivery mechanisms. They must never import web frameworks (FastAPI, Flask), CLI libraries (Click, Typer), or transport exceptions.
* **Enforcement:**
  * `.importlinter`: Contract `use_case_transport_isolation` forbids web and CLI packages.
  * `pytest_archon`: `test_use_cases_are_transport_and_framework_agnostic`.
* **Remediation:** Move transport parsing, HTTP status mapping, and CLI exit codes to driving adapters (`adapters/driving/`).

---

### HEXA-TRUTH-14: Stateless Interactor Invariants

* **Definition:** Use case instances are stateless orchestrators. Execution methods must not mutate instance attributes (`self.*`) outside `__init__`, guaranteeing thread and coroutine safety when reused as singletons.
* **Enforcement:**
  * `pytest_archon`: `test_use_cases_are_stateless_interactors`.
* **Remediation:** Pass state via method parameters and return values rather than storing intermediate results on `self`.

---

### HEXA-TRUTH-15: Zero Direct I/O Bypass

* **Definition:** Use cases must route all network, filesystem, and external device interactions through abstract driven ports. Use cases never directly import HTTP clients (`requests`, `httpx`), raw sockets, or direct disk-writing libraries.
* **Enforcement:**
  * `pytest_archon`: `test_use_cases_do_not_bypass_ports_with_direct_io`.
* **Remediation:** Create a driven port contract for the required I/O operation and implement it within an adapter in `adapters/driven/`.

---

### HEXA-TRUTH-16: Zero Implementation Code in Ports

* **Definition:** Ports in `core/ports/` are pure behavioral specifications. Method bodies must strictly contain ellipses (`...`) or `pass`. Ports must never define concrete attributes, initializers (`__init__`), or business logic.
* **Enforcement:**
  * `pytest_archon`: `test_ports_have_zero_implementation_code`.
* **Remediation:** Remove implementation logic from port methods, replacing bodies with `...`. Move concrete code into an adapter.

---

### HEXA-TRUTH-17: Technology-Agnostic Port Nomenclature

* **Definition:** Ports represent pure application capabilities and must be named without vendor or infrastructure keywords. Port class names must end with `Port` and never include terms like `Sql`, `Postgres`, `Redis`, `Http`, `FastApi`, or `Mongo`.
* **Enforcement:**
  * `pytest_archon`: `test_ports_follow_technology_agnostic_nomenclature`.
* **Remediation:** Rename the port to describe the domain intention (e.g. `UserRepositoryPort` instead of `PostgresUserPort`).

---

### HEXA-TRUTH-18: Strict Port Package Import Whitelist

* **Definition:** Port contracts must only import from standard typing and domain namespaces (`typing`, `abc`, `collections.abc`, standard primitives, and `core.domain`). Ports must never import external frameworks, database drivers, or adapter modules.
* **Enforcement:**
  * `pytest_archon`: `test_ports_adhere_to_strict_import_whitelist`.
* **Remediation:** Remove external imports from port files. Map external payloads to pure domain types before passing them through ports.

---

### HEXA-TRUTH-19: Composition Root Isolation

* **Definition:** The composition root (`bootstrap/`) is the sole structural authority responsible for instantiating concrete adapters, wiring dependency injection into use cases, and assembling executable entrypoints. Core layers (`core/domain/`, `core/ports/`, `core/use_cases/`) and adapters (`adapters/`) must never import from `bootstrap/`.
* **Enforcement:**
  * `.importlinter`: Contract `composition_root_isolation` strictly forbids imports of `bootstrap` from `core` and `adapters`.
  * `pytest_archon`: `test_composition_root_isolation` AST test asserts zero bootstrap imports in core and adapter packages.
* **Remediation:** Remove `bootstrap` imports from core and adapter files. Pass dependencies into constructors via dependency injection configured inside `bootstrap/container.py`.

---

### HEXA-TRUTH-20: Driving Port Directional Integrity & Use Case Exclusivity

* **Definition:** Driving ports define the application's exposed capabilities. They must reside in `core/ports/driving/`, inherit from `DrivingPort`, and be implemented exclusively by application use cases in `core/use_cases/`. Adapters must never implement driving ports (driving adapters invoke them).
* **Enforcement:**
  * `pytest_archon`: `test_driving_ports_directional_integrity_and_exclusivity`.
* **Remediation:** Ensure port contracts in `core/ports/driving/` inherit from `DrivingPort`. Move any adapter implementing a driving port into `core/use_cases/` or convert the adapter into a consumer calling the port.

---

### HEXA-TRUTH-21: Driven Port Inversion & Injection Governance

* **Definition:** Driven ports define the SPI dependencies the application requires from the environment. They must reside in `core/ports/driven/`, inherit from `DrivenPort`, and be implemented exclusively by driven adapters in `adapters/driven/`. Use cases must never implement driven ports and must accept them strictly via constructor dependency injection (`__init__`).
* **Enforcement:**
  * `pytest_archon`: `test_driven_ports_inversion_and_injection_governance`.
* **Remediation:** Ensure port contracts in `core/ports/driven/` inherit from `DrivenPort`. Ensure driven adapters implement the port, and inject the port interface into use cases via `__init__`.

---

### HEXA-TRUTH-22: Repository vs. Recipient Driven Port Semantics

* **Definition:** Driven ports must be classified either as a **Repository** (read/write methods returning domain state or models) or a **Recipient** (fire-and-forget notification methods returning `None` or boolean ACK). Driven ports must not conflate notification side effects with state persistence in a single interface.
* **Enforcement:**
  * `pytest_archon`: `test_driven_ports_repository_recipient_semantics`.
* **Remediation:** Split mixed ports into separate repository and recipient contracts. Ensure methods returning state adhere to repository semantics and notification methods return `None`.

---

### HEXA-TRUTH-23: Outbound Infrastructure Exception Masking

* **Definition:** Driven adapters must catch external infrastructure, network, database, and OS exceptions (`psycopg2`, `redis`, `boto3`, `OSError`) and translate them into domain-level port exceptions before re-raising. Third-party vendor exceptions must never leak across driven ports into the core domain.
* **Enforcement:**
  * `pytest_archon`: `test_outbound_infrastructure_exception_masking`.
* **Remediation:** Wrap external SDK or driver calls in `try...except` inside driven adapters and raise custom domain port exceptions inheriting from `DomainError`.

---

### HEXA-TRUTH-24: Driven Port Return Type Encapsulation

* **Definition:** Driven port methods must return domain models, value objects, or frozen DTOs. They must never return ORM querysets, raw database cursors, HTTP responses, or untyped dictionaries (`dict[str, Any]`).
* **Enforcement:**
  * `pytest_archon`: `test_driven_ports_return_type_encapsulation`.
* **Remediation:** Map database rows or raw API responses to pure domain models or frozen DTOs within the driven adapter before returning across the port.

---

### HEXA-TRUTH-25: Driving Port CQRS & Use Case Cohesion

* **Definition:** Driving ports represent single cohesive business capabilities or CQRS operations. They must never expose persistence-oriented CRUD primitives (`save`, `delete`, `find_by_id`, `update_row`).
* **Enforcement:**
  * `pytest_archon`: `test_driving_ports_cqrs_and_use_case_cohesion`.
* **Remediation:** Rename driving port operations to express domain business intentions (e.g. `check_health`, `register_user`, `calculate_invoice`) rather than database operations.

---

### HEXA-TRUTH-26: Caller & Transport Ignorance in Driving Signatures

* **Definition:** Driving port parameters must never accept transport-specific objects (`Request`, `Response`, `Header`, `Session`, `CliContext`). All parameters must be primitive scalars, value objects, or frozen input DTOs.
* **Enforcement:**
  * `pytest_archon`: `test_driving_ports_caller_and_transport_ignorance`.
* **Remediation:** Extract transport headers, cookies, and request bodies into pure domain DTOs inside the driving adapter before passing them into the driving port.

---

### HEXA-TRUTH-27: Dual-Adapter Test Double Parity

* **Definition:** Every driven port in `core/ports/driven/` must have a corresponding in-memory test double (stub or fake) residing in `tests/doubles/` satisfying the port protocol. This ensures that the application can be verified completely offline without live infrastructure.
* **Enforcement:**
  * `pytest_archon`: `test_driven_ports_test_double_parity`.
* **Remediation:** Author an in-memory double (e.g. `FakeSystemProbeAdapter`) in `tests/doubles/` using Python standard library collections (`dict`, `list`).

---

### HEXA-TRUTH-28: DTO Immutability & Structural Purity

* **Definition:** Data Transfer Objects crossing port boundaries must reside in `core/ports/` (co-located with driving or driven ports), be decorated as `@dataclass(frozen=True)` (or inherit `DataTransferObject`), and contain only whitelisted primitive scalars, immutable collections (`tuple`, `frozenset`), and domain value objects. DTOs must never contain mutable collections (`list`, `dict`), framework types, ORM models, or business methods.
* **Enforcement:**
  * `pytest_archon`: `test_dto_immutability_and_structural_purity`.
* **Remediation:** Decorate DTO classes with `@dataclass(frozen=True, slots=True)`, convert mutable lists or dicts into tuples or frozensets, and remove external framework imports.
