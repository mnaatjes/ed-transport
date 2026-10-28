---
title: "Configuration Value Objects Reference"
tags: ["configuration", "reference", "ratelimit", "retry", "spool"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# Configuration Value Objects Reference

This reference details the pure domain configuration value objects that govern rate-limiting, retry policies, and bounded offline spooling in `ed_transport`.

---

## 1. RateLimitConfig

Controls token bucket rate limits per destination.

```python
@dataclass(frozen=True)
class RateLimitConfig:
    requests_per_second: float = 5.0
    burst_capacity: int = 10
    destination_key: str = "default"
```

* `requests_per_second`: Continuous token generation frequency (tokens per second).
* `burst_capacity`: Maximum tokens accumulated in bucket when idle.
* `destination_key`: Default grouping identifier if URL netloc parsing is omitted.

---

## 2. RateLimitRule

Defines specific rate limit parameters matching destination patterns.

```python
@dataclass(frozen=True)
class RateLimitRule:
    destination_pattern: str
    requests_per_second: float = 5.0
    burst_capacity: int = 10
```

---

## 3. RetryConfig

Configures exponential backoff with randomized decorrelated jitter retry loops.

```python
@dataclass(frozen=True)
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 0.5
    max_backoff: float = 10.0
    retryable_statuses: frozenset[int] = frozenset({408, 429, 500, 502, 503, 504})
```

* `max_retries`: Maximum consecutive retry attempts before raising `MaxRetriesExceededError`.
* `base_delay`: Initial exponential backoff scaling factor in seconds.
* `max_backoff`: Upper ceiling cap for backoff sleep interval.
* `retryable_statuses`: Set of HTTP status codes that trigger a retry.

---

## 4. SpoolConfig

Governs memory limits, disk persistence, capacity limits, and corruption recovery for offline buffering.

```python
@dataclass(frozen=True)
class SpoolConfig:
    max_capacity: int = 1000
    memory_limit_bytes: int = 10 * 1024 * 1024  # 10 MB default
    eviction_policy: str = "DropOldest"         # "DropOldest" or "RejectNewest"
    storage_path: str = ""                       # Empty = in-memory buffer
    auto_recover_corrupt: bool = False           # If True, re-creates corrupt db
```

* `max_capacity`: Maximum number of requests allowed in the queue.
* `memory_limit_bytes`: Aggregate bytes allowed across stored payloads.
* `eviction_policy`: Policy when capacity is saturated (`DropOldest` removes oldest FIFO record; `RejectNewest` raises `SpoolCapacityExceededError`).
* `storage_path`: Filesystem path to SQLite database. If empty, strictly runs in-memory (`MemorySpoolStorageAdapter`), adhering to library invariants.
* `auto_recover_corrupt`: If `True`, quarantines corrupted SQLite files (`.corrupt.<timestamp>`) and reinitializes a fresh database schema. If `False`, raises `SpoolStorageCorruptError`.
