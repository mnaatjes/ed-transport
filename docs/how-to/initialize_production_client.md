---
title: "How-To: Initialize Production Clients"
tags: ["how-to", "factory", "bootstrap", "client"]
created_at: "2026-10-28"
last_updated_at: "2026-10-28"
---

# How-To: Initialize Production Clients

This guide describes how downstream libraries (`ed-capi`, `ed-eddn`, `ed-connectors`) instantiate fully wired `TransportClient` and `AsyncTransportClient` instances using factory functions.

---

## 1. Synchronous Client Initialization

Use `create_transport_client()` to construct a synchronous client wired with httpx engine dispatch, token bucket rate limiting, and circular spooling:

```python
from ed_transport import create_transport_client

# Instant, zero-config in-memory client
client = create_transport_client()
try:
    resp = client.get("https://api.frontier.ed/status")
    print(resp.status_code, resp.text)
finally:
    client.close()
```

Or using a context manager:

```python
with create_transport_client() as client:
    resp = client.get("https://api.frontier.ed/status")
    print(resp.status_code)
```

---

## 2. Asynchronous Client Initialization

For reactive event loops, daemons, or telemetry streaming, use `create_async_transport_client()`:

```python
import asyncio
from ed_transport import create_async_transport_client

async def main() -> None:
    async with create_async_transport_client() as client:
        resp = await client.get_async("https://api.frontier.ed/status")
        print(resp.status_code)

asyncio.run(main())
```

---

## 3. Customizing Storage and Retry Bounds

```python
from ed_transport import create_transport_client
from ed_transport.core.domain.models import RetryConfig, SpoolConfig

retry_cfg = RetryConfig(max_retries=5, base_delay=0.2, max_backoff=5.0)
spool_cfg = SpoolConfig(storage_path="/var/tmp/ed_spool.db", auto_recover_corrupt=True)

with create_transport_client(retry_config=retry_cfg, spool_config=spool_cfg) as client:
    client.send_buffered(url="https://eddn.edcd.io/upload/", method="POST", body=b"{}")
```
