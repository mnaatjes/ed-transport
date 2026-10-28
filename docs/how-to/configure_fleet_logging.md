---
title: "How-To: Configure Fleet Daemon Logging"
tags: ["how-to", "logging", "daemon", "bootstrap", "persistence"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# How-To: Configure Fleet Daemon Logging

This guide explains how standalone daemon packages (`ed-capi`, `ed-eddn`, `ed-connectors`) initialize standardized, rotating file logging using `ed-transport`'s bootstrap helper.

---

## 1. Initializing Logging at Daemon Startup

In the entrypoint of your daemon application (e.g., `main.py` or CLI click/typer command), invoke `configure_fleet_logging`:

```python
import logging
from ed_transport.bootstrap import configure_fleet_logging

def main() -> None:
    # Sets up rotating file logging in the standard platform directory
    log_path = configure_fleet_logging(
        app_name="ed-capi",
        level=logging.INFO,
        max_bytes=5 * 1024 * 1024,  # 5 MB per file
        backup_count=5,             # 5 backup files (max 25 MB total)
    )
    print(f"Logging active at: {log_path}")

    # Now all ed_transport and daemon log records route to this file automatically
```

---

## 2. Standard Platform Storage Locations

`configure_fleet_logging` adheres to Homelab Systems Lifecycle filesystem conventions:

* **Linux / Steam Deck (Proton):**
  `~/.local/state/<app_name>/logs/<app_name>.log`
* **Windows NT Native:**
  `%LOCALAPPDATA%\<app_name>\logs\<app_name>.log`

### Custom Log Directory

To specify an explicit custom log directory (e.g. for integration tests or container mounts):

```python
from pathlib import Path
from ed_transport.bootstrap import configure_fleet_logging

log_path = configure_fleet_logging(
    app_name="ed-eddn",
    log_dir=Path("/var/log/ed-fleet"),
)
```

---

## 3. Log Rotation Behavior

The logger utilizes `logging.handlers.RotatingFileHandler`:
1. When `<app_name>.log` reaches `max_bytes`, it is closed and renamed to `<app_name>.log.1`.
2. Existing backup files are bumped (`.1` -> `.2`, etc.).
3. When `backup_count` is reached, the oldest log file is deleted automatically.
4. Total disk usage is strictly bounded: $\text{Disk Limit} = \text{max\_bytes} \times (\text{backup\_count} + 1)$.
