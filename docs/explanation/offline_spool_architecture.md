---
title: "Architecture: Offline Spool Subsystem"
tags: ["explanation", "architecture", "spool", "sqlite", "resilience"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# Architecture: Offline Spool Subsystem

This document provides an architectural deep dive into the offline request spooling mechanism in `ed_transport`, explaining storage abstractions, concurrency controls, and corruption resilience.

---

## 1. Hexagonal Separation of Concerns

The offline spooling system strictly decouples the domain business intention from storage technology:

* **Driving Port (`SpoolManagerPort`):** Exposes caller methods (`enqueue`, `drain`, `depth`) for adding and flushing buffered requests.
* **Use Case Interactor (`DrainSpoolBufferUseCase`):** Coordinates fetching records from storage in FIFO order and executing them against `TransportPort`.
* **Driven Port (`SpoolStoragePort`):** Defines technology-agnostic secondary SPI contracts (`push`, `pop`, `peek`, `count`, `size_bytes`).
* **Driven Adapters:**
  * `MemorySpoolStorageAdapter`: Fast in-memory deque buffer with zero disk footprints.
  * `SqliteSpoolStorageAdapter`: Disk-persisted circular queue using SQLite.

---

## 2. Concurrency and Durability Guarantees

When using SQLite persistence (`SqliteSpoolStorageAdapter`):

1. **Write-Ahead Logging (WAL):** Connections are initialized with `PRAGMA journal_mode=WAL;`, enabling simultaneous readers and writers without database locking collisions.
2. **Busy Timeout:** Configured with `PRAGMA busy_timeout=5000;` to gracefully wait up to 5 seconds during concurrent operations.
3. **Re-entrant Thread Lock:** All read/write operations pass through a `threading.RLock`, ensuring thread-safe access within multi-threaded processes.

---

## 3. Library Lifecycle Invariants

In compliance with ADR-0005:

1. **Zero Unprompted Disk Files:** If `storage_path` is left empty, the engine strictly uses `MemorySpoolStorageAdapter`. Disk files are never created unprompted.
2. **No Background Worker Threads:** The spooling subsystem never creates unmanaged daemon threads or timer loops. Draining runs strictly on-demand when `client.drain_spool()` or `await client.drain_spool_async()` is invoked by the host application.
3. **Controlled Corruption Recovery:** If a SQLite database is corrupted (e.g. abrupt power failure on Steam Deck), the adapter raises `SpoolStorageCorruptError` unless the caller explicitly opted into auto-recovery via `SpoolConfig(auto_recover_corrupt=True)`.
