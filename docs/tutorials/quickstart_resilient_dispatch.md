---
title: "Quickstart: Resilient HTTP Dispatch"
tags: ["tutorial", "quickstart", "dispatch", "beginner"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# Quickstart: Resilient HTTP Dispatch

This tutorial walks through dispatching network requests, handling rate limiting backpressure, and spooling requests while offline using `ed_transport`.

---

## 1. Prerequisites

Install `ed_transport` within your active virtual environment:

```bash
pip install ed-transport
```

---

## 2. Dispatching a Simple Request

Create a basic Python script `example.py`:

```python
from ed_transport import create_transport_client

with create_transport_client() as client:
    response = client.get("https://httpbin.org/get")
    print("Status:", response.status_code)
    print("Body:", response.text)
```

Run the script:

```bash
python example.py
```

The client automatically managed the HTTP socket connection, evaluated destination rate limits, and safely released resources upon exiting the `with` block.

---

## 3. Handling Offline Network Drops

When sending critical telemetry that must not be dropped during network blips or offline play:

```python
import json
from ed_transport import create_transport_client
from ed_transport.core.domain.models import SpoolConfig

spool_cfg = SpoolConfig(storage_path="./offline_spool.db")

with create_transport_client(spool_config=spool_cfg) as client:
    payload = json.dumps({"event": "Docked", "StationName": "Jameson Memorial"})
    # Attempts immediate send; buffers to offline_spool.db on disconnect
    client.send_buffered(
        url="https://api.frontier.ed/journal",
        method="POST",
        body=payload,
    )
    print("Spool queue depth:", client.spool_depth)

    # When connectivity returns, drain the queue
    drained = client.drain_spool()
    print("Flushed records:", drained)
```
