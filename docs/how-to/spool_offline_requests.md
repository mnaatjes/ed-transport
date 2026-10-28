---
title: "How-To: Spool Offline Requests"
tags: ["how-to", "transport-client", "offline", "spooling", "resilience"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# How-To: Spool Offline Requests

This guide demonstrates how to buffer telemetry and event payloads during offline periods and flush the queue upon reconnecting using `send_buffered()` and `drain_spool()`.

---

## 1. Buffering Requests with `send_buffered`

When network conditions are transient or completely disconnected, use `send_buffered()` instead of standard `post()` or `put()`. If the immediate dispatch fails or the transport port reports connectivity loss, the request is stored in the bounded offline spool buffer.

### Synchronous Buffering Example

```python
import json
from ed_transport.adapters.driving import TransportClient
from ed_transport.core.domain.models import SpoolConfig

# Configure bounded spool (e.g. 20 MB max buffer)
spool_cfg = SpoolConfig(
    max_capacity_bytes=20 * 1024 * 1024,
    overflow_strategy="drop_oldest"
)

with TransportClient(
    transport_port=http_port,
    spool_port=spool_adapter,
    spool_config=spool_cfg
) as client:
    event_payload = json.dumps({
        "event": "FSDJump",
        "StarSystem": "Sol",
        "timestamp": "3310-10-28T12:00:00Z"
    })

    # Returns True if dispatched immediately or successfully queued in spool
    enqueued_or_sent = client.send_buffered(
        url="https://eddn.edcd.io:4430/upload/",
        method="POST",
        body=event_payload,
        headers={"Content-Type": "application/json"}
    )
    print(f"Request accepted: {enqueued_or_sent}")
```

---

## 2. Monitoring Spool Depth

You can inspect the number of pending buffered requests at any time via the `spool_depth` property:

```python
depth = client.spool_depth
print(f"Currently queued offline requests: {depth}")
```

---

## 3. Draining Buffered Requests

Once network connectivity is reestablished, trigger `drain_spool()` to flush queued requests sequentially in FIFO order:

```python
# Synchronous drain:
flushed_count = client.drain_spool()
print(f"Flushed {flushed_count} requests to remote endpoints.")
```

### Asynchronous Draining (`AsyncTransportClient`)

```python
async with AsyncTransportClient(
    transport_port=async_http_port,
    spool_port=spool_adapter
) as client:
    # Buffer event
    await client.send_buffered(
        url="https://eddn.edcd.io:4430/upload/",
        body=event_bytes
    )

    # Reconnect and drain
    flushed = await client.drain_spool()
    print(f"Flushed {flushed} items asynchronously.")
```

> [!NOTE]
> If no `spool_port` is passed to the client constructor, `send_buffered()` falls back to immediate unbuffered dispatch and `drain_spool()` returns `0`.
